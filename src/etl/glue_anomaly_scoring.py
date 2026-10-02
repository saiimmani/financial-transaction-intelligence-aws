"""Optional AWS Glue Spark job for a second-pass anomaly score.

This Glue-native score is deterministic and scalable: it reuses the engineered
transaction features from Silver and writes a second scored layer. The local
demo additionally uses Isolation Forest for unsupervised ML.
"""
from __future__ import annotations

import sys
from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from pyspark.sql import functions as F

args = getResolvedOptions(sys.argv, ["JOB_NAME", "SILVER_PATH", "OUTPUT_PATH"])
sc = SparkContext()
glue_context = GlueContext(sc)
spark = glue_context.spark_session
job = Job(glue_context)
job.init(args["JOB_NAME"], args)

silver = spark.read.parquet(args["SILVER_PATH"])

score = (
    F.least(F.col("sender_amount_zscore") / F.lit(10.0), F.lit(1.0)) * F.lit(40.0)
    + F.least(F.col("velocity_1h") / F.lit(10.0), F.lit(1.0)) * F.lit(30.0)
    + F.col("cross_border_flag") * F.lit(10.0)
    + F.col("high_value_flag") * F.lit(20.0)
)

scored = (
    silver.withColumn("secondary_anomaly_score", F.round(score, 2))
    .withColumn("secondary_anomaly_flag", (F.col("secondary_anomaly_score") >= 50).cast("int"))
)

scored.write.mode("overwrite").partitionBy("year", "month", "day").parquet(args["OUTPUT_PATH"])
job.commit()
