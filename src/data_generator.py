"""Generate reproducible synthetic financial transactions with planted anomalies."""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

COUNTRIES = ["IN", "US", "GB", "SG", "AE", "DE", "AU", "CA"]
CURRENCIES = ["INR", "USD", "GBP", "SGD", "AED", "EUR", "AUD", "CAD"]
MERCHANTS = ["GROCERY", "TRAVEL", "RESTAURANT", "ELECTRONICS", "UTILITIES", "HEALTHCARE", "ECOMMERCE"]
CHANNELS = ["MOBILE", "WEB", "POS", "ATM"]
DEVICES = ["ANDROID", "IOS", "WEB", "POS_TERMINAL"]
TX_TYPES = ["PURCHASE", "TRANSFER", "WITHDRAWAL", "PAYMENT", "REFUND"]


def generate_transactions(rows: int = 20000, seed: int = 42) -> pd.DataFrame:
    if rows < 500:
        raise ValueError("rows must be >= 500")
    rng = np.random.default_rng(seed)
    start = pd.Timestamp("2026-01-01T00:00:00Z")
    timestamps = (start + pd.to_timedelta(rng.integers(0, 90 * 24 * 3600, size=rows), unit="s")).to_numpy()

    customers = rng.integers(10000, 11500, size=rows)
    sender_account = rng.integers(200000, 202000, size=rows)
    receiver_account = rng.integers(300000, 304000, size=rows)
    sender_country = rng.choice(COUNTRIES, size=rows, p=[0.45, 0.12, 0.08, 0.08, 0.10, 0.06, 0.06, 0.05])
    receiver_country = sender_country.copy()
    cross_border_mask = rng.random(rows) < 0.12
    receiver_country[cross_border_mask] = rng.choice(COUNTRIES, size=int(cross_border_mask.sum()))

    currency_map = dict(zip(COUNTRIES, CURRENCIES))
    currency = np.array([currency_map[c] for c in sender_country])

    amount = np.exp(rng.normal(np.log(2200), 0.9, size=rows)).round(2)
    merchant_category = rng.choice(MERCHANTS, size=rows)
    channel = rng.choice(CHANNELS, size=rows, p=[0.35, 0.25, 0.30, 0.10])
    device_type = rng.choice(DEVICES, size=rows, p=[0.40, 0.30, 0.20, 0.10])
    transaction_type = rng.choice(TX_TYPES, size=rows, p=[0.40, 0.24, 0.08, 0.23, 0.05])

    ground_truth_anomaly = np.zeros(rows, dtype=int)
    anomaly_type = np.full(rows, "NONE", dtype=object)

    # Plant three interpretable anomaly families.
    n_each = max(15, rows // 500)
    indices = rng.choice(rows, size=n_each * 3, replace=False)
    high_value_idx = indices[:n_each]
    velocity_idx = indices[n_each : 2 * n_each]
    cross_border_idx = indices[2 * n_each :]

    amount[high_value_idx] *= rng.uniform(20, 60, size=n_each)
    ground_truth_anomaly[high_value_idx] = 1
    anomaly_type[high_value_idx] = "HIGH_VALUE"

    # Put high-velocity records into a tight time window and reuse one sender.
    hot_sender = sender_account[velocity_idx[0]]
    sender_account[velocity_idx] = hot_sender
    base_time = timestamps[velocity_idx[0]]
    timestamps[velocity_idx] = base_time + pd.to_timedelta(np.arange(n_each) * 45, unit="s")
    amount[velocity_idx] = rng.uniform(1000, 5000, size=n_each)
    ground_truth_anomaly[velocity_idx] = 1
    anomaly_type[velocity_idx] = "VELOCITY_SPIKE"

    # Unusual cross-border behavior.
    sender_country[cross_border_idx] = "IN"
    receiver_country[cross_border_idx] = rng.choice(["US", "GB", "SG", "AE"], size=n_each)
    currency[cross_border_idx] = "INR"
    device_type[cross_border_idx] = "WEB"
    ground_truth_anomaly[cross_border_idx] = 1
    anomaly_type[cross_border_idx] = "CROSS_BORDER"

    # Introduce a small amount of data quality noise that the ETL should quarantine.
    bad_count = max(10, rows // 1000)
    bad_idx = rng.choice(np.arange(rows), size=bad_count, replace=False)
    amount[bad_idx[: bad_count // 2]] = -rng.uniform(1, 200, size=bad_count // 2)
    tx_id = np.array([f"TXN-{i:08d}" for i in range(rows)])
    customer_id = np.array([f"CUS-{x:06d}" for x in customers])
    sender = np.array([f"ACC-{x:08d}" for x in sender_account])
    receiver = np.array([f"ACC-{x:08d}" for x in receiver_account])

    return pd.DataFrame(
        {
            "transaction_id": tx_id,
            "transaction_timestamp": timestamps,
            "customer_id": customer_id,
            "sender_account": sender,
            "receiver_account": receiver,
            "sender_country": sender_country,
            "receiver_country": receiver_country,
            "currency": currency,
            "amount": amount,
            "transaction_type": transaction_type,
            "merchant_category": merchant_category,
            "channel": channel,
            "device_type": device_type,
            "ground_truth_anomaly": ground_truth_anomaly,
            "anomaly_type": anomaly_type,
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", default="data/transactions_raw.csv")
    args = parser.parse_args()
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    df = generate_transactions(args.rows, args.seed)
    df.to_csv(out, index=False)
    print(f"Wrote {len(df):,} transactions to {out}")
    print(f"Planted anomalies: {int(df['ground_truth_anomaly'].sum()):,}")


if __name__ == "__main__":
    main()
