-- Financial Transaction Analytics warehouse schema
-- Run in Amazon Redshift / Redshift Serverless Query Editor v2.

CREATE SCHEMA IF NOT EXISTS analytics;

CREATE TABLE IF NOT EXISTS analytics.fact_transactions (
    transaction_id VARCHAR(32) NOT NULL,
    transaction_timestamp TIMESTAMP NOT NULL,
    customer_id VARCHAR(32),
    sender_account VARCHAR(32),
    receiver_account VARCHAR(32),
    sender_country VARCHAR(3),
    receiver_country VARCHAR(3),
    currency VARCHAR(8),
    amount DECIMAL(18,2),
    transaction_type VARCHAR(32),
    merchant_category VARCHAR(64),
    channel VARCHAR(32),
    device_type VARCHAR(32),
    cross_border_flag SMALLINT,
    sender_amount_zscore DOUBLE PRECISION,
    velocity_1h INTEGER,
    high_value_flag SMALLINT,
    rule_anomaly_score DOUBLE PRECISION,
    ml_anomaly_score DOUBLE PRECISION,
    anomaly_score DOUBLE PRECISION,
    anomaly_flag SMALLINT,
    anomaly_severity VARCHAR(16),
    anomaly_reason VARCHAR(256),
    year SMALLINT,
    month SMALLINT,
    day SMALLINT,
    PRIMARY KEY (transaction_id)
)
DISTSTYLE AUTO
SORTKEY (transaction_timestamp, sender_country, anomaly_flag);

CREATE TABLE IF NOT EXISTS analytics.dim_date (
    date_key DATE PRIMARY KEY,
    year SMALLINT,
    quarter SMALLINT,
    month SMALLINT,
    month_name VARCHAR(12),
    day_of_month SMALLINT,
    day_of_week SMALLINT,
    day_name VARCHAR(12),
    is_weekend BOOLEAN
)
DISTSTYLE AUTO
SORTKEY(date_key);

-- After Glue writes Silver Parquet, use COPY with IAM_ROLE to load the fact table.
-- Replace <REGION>, <BUCKET>, and <ROLE_ARN>.
-- Example:
-- COPY analytics.fact_transactions
-- FROM 's3://<BUCKET>/silver/transactions/'
-- IAM_ROLE '<ROLE_ARN>'
-- FORMAT AS PARQUET;
