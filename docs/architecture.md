# Architecture and design notes

## Business problem

Financial systems receive large numbers of transactions from multiple channels. Analysts need a repeatable way to ingest, clean, standardize, monitor, and analyze transactions while surfacing unusual patterns for review.

## Architecture

```text
                    +-----------------------+
                    | Financial source data |
                    | CSV / API / JSON      |
                    +-----------+-----------+
                                |
                                v
                       +------------------+
                       | Amazon S3        |
                       | Bronze / Raw     |
                       +---------+--------+
                                 |
                                 v
                       +------------------+
                       | AWS Glue 6.0     |
                       | PySpark ETL      |
                       | quality checks   |
                       +---------+--------+
                                 |
                +----------------+----------------+
                |                                 |
                v                                 v
       +------------------+                +----------------+
       | S3 Silver        |                | S3 Quarantine  |
       | Parquet          |                | invalid rows   |
       +--------+---------+                +----------------+
                |
                v
       +------------------+
       | S3 Gold          |
       | BI aggregates    |
       +--------+---------+
                |
                v
       +------------------+
       | Amazon Redshift  |
       | analytics schema |
       +--------+---------+
                |
        +-------+-------+
        |               |
        v               v
   SQL views        Power BI
        |
        v
  anomaly review
```

## Anomaly model

The local model uses two layers:

1. **Explainable rules**: sender-relative amount deviation, one-hour transaction velocity, cross-border activity, and high-value activity.
2. **Isolation Forest**: unsupervised machine learning over engineered numeric and categorical features.

The final score is:

`0.60 * rule_score + 0.40 * ml_score`

The synthetic dataset includes a ground-truth label solely for evaluation. The detector does not consume that label during training.

## AWS anomaly/data-quality extension

AWS Glue Data Quality can additionally monitor data statistics over time and detect anomalies using historical trends. It supports anomaly detection in Glue ETL and the Data Catalog. See AWS documentation for `DetectAnomalies` and Glue Data Quality. This project keeps transaction-level anomaly scoring separate from pipeline-level data-quality monitoring so the two concepts remain clear.
