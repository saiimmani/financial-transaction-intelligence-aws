CREATE OR REPLACE VIEW analytics.v_daily_transaction_kpis AS
SELECT
    CAST(transaction_timestamp AS DATE) AS transaction_date,
    COUNT(*) AS transaction_count,
    SUM(amount) AS total_amount,
    AVG(amount) AS average_amount,
    SUM(anomaly_flag) AS anomalous_transactions,
    ROUND(100.0 * SUM(anomaly_flag) / NULLIF(COUNT(*), 0), 2) AS anomaly_rate_pct
FROM analytics.fact_transactions
GROUP BY 1;

CREATE OR REPLACE VIEW analytics.v_country_flow AS
SELECT
    sender_country,
    receiver_country,
    COUNT(*) AS transaction_count,
    SUM(amount) AS total_amount,
    SUM(anomaly_flag) AS anomalous_transactions,
    ROUND(100.0 * SUM(anomaly_flag) / NULLIF(COUNT(*), 0), 2) AS anomaly_rate_pct
FROM analytics.fact_transactions
GROUP BY 1, 2;

CREATE OR REPLACE VIEW analytics.v_channel_kpis AS
SELECT
    channel,
    COUNT(*) AS transaction_count,
    SUM(amount) AS total_amount,
    AVG(amount) AS average_amount,
    SUM(anomaly_flag) AS anomalous_transactions
FROM analytics.fact_transactions
GROUP BY 1;

CREATE OR REPLACE VIEW analytics.v_category_kpis AS
SELECT
    merchant_category,
    COUNT(*) AS transaction_count,
    SUM(amount) AS total_amount,
    AVG(amount) AS average_amount,
    SUM(anomaly_flag) AS anomalous_transactions
FROM analytics.fact_transactions
GROUP BY 1;

CREATE OR REPLACE VIEW analytics.v_high_risk_transactions AS
SELECT *
FROM analytics.fact_transactions
WHERE anomaly_flag = 1
ORDER BY anomaly_score DESC, transaction_timestamp DESC;
