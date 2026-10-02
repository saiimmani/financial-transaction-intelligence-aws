# Data dictionary

| Column | Description |
|---|---|
| transaction_id | Unique transaction identifier |
| transaction_timestamp | UTC transaction timestamp |
| customer_id | Synthetic customer identifier |
| sender_account | Synthetic sender account |
| receiver_account | Synthetic receiver account |
| sender_country | Sender country code |
| receiver_country | Receiver country code |
| currency | Source currency |
| amount | Transaction amount |
| transaction_type | Purchase, transfer, withdrawal, payment, refund |
| merchant_category | Business category |
| channel | Mobile, web, POS, ATM |
| device_type | Synthetic device/channel technology |
| cross_border_flag | 1 when sender and receiver countries differ |
| sender_amount_zscore | Sender-relative robust amount deviation |
| velocity_1h | Sender transaction count in preceding hour |
| high_value_flag | 1 when transaction is in the top 0.5% of the current batch |
| rule_anomaly_score | Explainable rule score from 0 to 100 |
| ml_anomaly_score | Isolation Forest-derived score from 0 to 100 |
| anomaly_score | Weighted combined anomaly score |
| anomaly_flag | 1 when final score is at least 50 |
| anomaly_severity | LOW / MEDIUM / HIGH / CRITICAL |
| anomaly_reason | Human-readable anomaly indicators |
