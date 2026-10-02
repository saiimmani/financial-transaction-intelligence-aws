"""AWS Glue 6.0 PySpark ETL job.

Bronze CSV in S3 -> Silver Parquet -> Gold Parquet + quarantine.
This script intentionally keeps transaction anomaly scoring explainable so it can
run without shipping scikit-learn into the Glue runtime.
"""
from __future__ import annotations

import sys
from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from pyspark.sql import functions as F
from pyspark.sql.window import Window

args = getResolvedOptions(
    sys.argv,
    [
        "JOB_NAME",
        "SOURCE_PATH",
        "SILVER_PATH",
        "GOLD_PATH",
        "QUARANTINE_PATH",
    ],
)

sc = SparkContext()
glue_context = GlueContext(sc)
spark = glue_context.spark_session
job = Job(glue_context)
job.init(args["JOB_NAME"], args)

source = args["SOURCE_PATH"]
silver_path = args["SILVER_PATH"]
gold_path = args["GOLD_PATH"]
quarantine_path = args["QUARANTINE_PATH"]

required = [
    "transaction_id", "transaction_timestamp", "customer_id", "sender_account",
    "receiver_account", "sender_country", "receiver_country", "currency", "amount",
    "transaction_type", "merchant_category", "channel", "device_type",
]

raw = (
    spark.read
    .option("header", True)
    .option("inferSchema", True)
    .csv(source)
)

# Schema contract: add missing columns as strings so the job remains resilient to source drift.
for col_name in required:
    if col_name not in raw.columns:
        raw = raw.withColumn(col_name, F.lit(None).cast("string"))

raw = raw.select(*required)

normalized = (
    raw
    .withColumn("transaction_timestamp", F.to_timestamp("transaction_timestamp"))
    .withColumn("amount", F.col("amount").cast("double"))
)

invalid = normalized.filter(
    F.col("transaction_id").isNull()
    | F.col("transaction_timestamp").isNull()
    | F.col("amount").isNull()
    | (F.col("amount") <= 0)
    | F.col("sender_account").isNull()
    | F.col("receiver_account").isNull()
)

invalid.write.mode("append").format("parquet").save(quarantine_path)

valid = normalized.join(
    invalid.select("transaction_id").distinct(),
    on="transaction_id",
    how="left_anti",
)

silver = (
    valid
    .withColumn("sender_country", F.upper(F.trim("sender_country")))
    .withColumn("receiver_country", F.upper(F.trim("receiver_country")))
    .withColumn("currency", F.upper(F.trim("currency")))
    .withColumn("transaction_type", F.upper(F.trim("transaction_type")))
    .withColumn("merchant_category", F.upper(F.trim("merchant_category")))
    .withColumn("channel", F.upper(F.trim("channel")))
    .withColumn("device_type", F.upper(F.trim("device_type")))
    .dropDuplicates(["transaction_id"])
    .withColumn("cross_border_flag", (F.col("sender_country") != F.col("receiver_country")).cast("int"))
)

sender_window = Window.partitionBy("sender_account")
silver = (
    silver
    .withColumn("sender_mean", F.avg("amount").over(sender_window))
    .withColumn("sender_std", F.stddev_pop("amount").over(sender_window))
    .withColumn(
        "sender_amount_zscore",
        F.when(
            F.col("sender_std") > 0,
            F.abs(F.col("amount") - F.col("sender_mean")) / F.col("sender_std"),
        ).otherwise(F.lit(0.0)),
    )
)

velocity_window = (
    Window.partitionBy("sender_account")
    .orderBy(F.col("transaction_timestamp").cast("long"))
    .rangeBetween(-3600, -1)
)
silver = silver.withColumn("velocity_1h", F.count("transaction_id").over(velocity_window))

quantile = silver.approxQuantile("amount", [0.995], 0.01)
high_value_threshold = quantile[0] if quantile else 0.0
silver = silver.withColumn(
    "high_value_flag", (F.col("amount") >= F.lit(high_value_threshold)).cast("int")
)

silver = silver.withColumn(
    "rule_anomaly_score",
    (
        F.least(F.col("sender_amount_zscore") / F.lit(10.0), F.lit(1.0)) * F.lit(35.0)
        + F.least(F.col("velocity_1h") / F.lit(10.0), F.lit(1.0)) * F.lit(25.0)
        + F.col("cross_border_flag") * F.lit(15.0)
        + F.col("high_value_flag") * F.lit(25.0)
    ),
)

silver = (
    silver
    .withColumn("anomaly_score", F.round(F.col("rule_anomaly_score"), 2))
    .withColumn("anomaly_flag", (F.col("anomaly_score") >= 50).cast("int"))
    .withColumn(
        "anomaly_severity",
        F.when(F.col("anomaly_score") >= 75, "CRITICAL")
        .when(F.col("anomaly_score") >= 50, "HIGH")
        .when(F.col("anomaly_score") >= 25, "MEDIUM")
        .otherwise("LOW"),
    )
    .withColumn(
        "anomaly_reason",
        F.concat_ws(
            "|",
            F.when(F.col("sender_amount_zscore") >= 3, "UNUSUAL_AMOUNT"),
            F.when(F.col("velocity_1h") >= 6, "HIGH_VELOCITY"),
            F.when(F.col("cross_border_flag") == 1, "CROSS_BORDER"),
            F.when(F.col("high_value_flag") == 1, "HIGH_VALUE"),
        ),
    )
    .withColumn("year", F.year("transaction_timestamp"))
    .withColumn("month", F.month("transaction_timestamp"))
    .withColumn("day", F.dayofmonth("transaction_timestamp"))
)

# Replace empty reason with MODEL_SIGNAL.
silver = silver.withColumn(
    "anomaly_reason",
    F.when(F.length(F.col("anomaly_reason")) == 0, F.lit("MODEL_SIGNAL"))
    .otherwise(F.col("anomaly_reason")),
)

silver.write.mode("overwrite").partitionBy("year", "month", "day").parquet(silver_path)

# Gold layer: small curated tables intended for BI.
bronze_cols = silver.columns

daily = (
    silver.withColumn("date", F.to_date("transaction_timestamp"))
    .groupBy("date")
    .agg(
        F.count("transaction_id").alias("transaction_count"),
        F.sum("amount").alias("total_amount"),
        F.avg("amount").alias("average_amount"),
        F.sum("anomaly_flag").alias("anomalous_transactions"),
    )
    .withColumn("anomaly_rate", F.col("anomalous_transactions") / F.col("transaction_count"))
)

country = silver.groupBy("sender_country", "receiver_country").agg(
    F.count("transaction_id").alias("transaction_count"),
    F.sum("amount").alias("total_amount"),
    F.sum("anomaly_flag").alias("anomalous_transactions"),
)

channel = silver.groupBy("channel").agg(
    F.count("transaction_id").alias("transaction_count"),
    F.sum("amount").alias("total_amount"),
    F.avg("amount").alias("average_amount"),
    F.sum("anomaly_flag").alias("anomalous_transactions"),
)

category = silver.groupBy("merchant_category").agg(
    F.count("transaction_id").alias("transaction_count"),
    F.sum("amount").alias("total_amount"),
    F.avg("amount").alias("average_amount"),
    F.sum("anomaly_flag").alias("anomalous_transactions"),
)

anomalies = silver.filter(F.col("anomaly_flag") == 1)

for name, frame in {
    "daily_kpi": daily,
    "country_flow": country,
    "channel_kpi": channel,
    "category_kpi": category,
    "anomalies": anomalies,
}.items():
    frame.write.mode("overwrite").parquet(f"{gold_path}/{name}/")

job.commit()
