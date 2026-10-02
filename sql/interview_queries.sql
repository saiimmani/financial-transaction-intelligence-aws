-- 1. Top 10 suspicious transactions
SELECT transaction_id, transaction_timestamp, amount, sender_account,
       sender_country, receiver_country, anomaly_score, anomaly_reason
FROM analytics.fact_transactions
WHERE anomaly_flag = 1
ORDER BY anomaly_score DESC
LIMIT 10;

-- 2. Daily anomaly trend
SELECT *
FROM analytics.v_daily_transaction_kpis
ORDER BY transaction_date;

-- 3. Highest-risk country corridors
SELECT sender_country, receiver_country,
       COUNT(*) AS transactions,
       SUM(anomaly_flag) AS anomalies,
       ROUND(100.0 * SUM(anomaly_flag) / NULLIF(COUNT(*),0), 2) AS anomaly_rate_pct
FROM analytics.fact_transactions
GROUP BY 1,2
HAVING COUNT(*) >= 10
ORDER BY anomaly_rate_pct DESC;

-- 4. Channels with unusual transaction frequency
SELECT channel,
       COUNT(*) AS transactions,
       SUM(anomaly_flag) AS anomalies,
       AVG(amount) AS average_amount
FROM analytics.fact_transactions
GROUP BY 1
ORDER BY anomalies DESC;

-- 5. High-velocity sender accounts
SELECT sender_account,
       COUNT(*) AS transaction_count,
       MAX(velocity_1h) AS max_velocity_1h,
       SUM(anomaly_flag) AS anomalies
FROM analytics.fact_transactions
GROUP BY 1
HAVING MAX(velocity_1h) >= 6
ORDER BY max_velocity_1h DESC;

-- 6. High-value transaction concentration
SELECT merchant_category,
       COUNT(*) AS transactions,
       SUM(amount) AS total_amount,
       MAX(amount) AS max_amount,
       SUM(high_value_flag) AS high_value_transactions
FROM analytics.fact_transactions
GROUP BY 1
ORDER BY total_amount DESC;
