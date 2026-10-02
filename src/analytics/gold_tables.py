"""Build local Gold-layer CSV tables suitable for Power BI."""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def build_gold(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    work = df.copy()
    work["transaction_timestamp"] = pd.to_datetime(work["transaction_timestamp"], utc=True)
    work["date"] = work["transaction_timestamp"].dt.date.astype(str)
    work["month"] = work["transaction_timestamp"].dt.strftime("%Y-%m")
    work["is_anomalous"] = work["anomaly_flag"].astype(int)

    daily = (
        work.groupby("date", as_index=False)
        .agg(
            transaction_count=("transaction_id", "count"),
            total_amount=("amount", "sum"),
            average_amount=("amount", "mean"),
            anomalous_transactions=("is_anomalous", "sum"),
        )
    )
    daily["anomaly_rate"] = daily["anomalous_transactions"] / daily["transaction_count"]

    country = (
        work.groupby(["sender_country", "receiver_country"], as_index=False)
        .agg(
            transaction_count=("transaction_id", "count"),
            total_amount=("amount", "sum"),
            anomalous_transactions=("is_anomalous", "sum"),
        )
        .sort_values("total_amount", ascending=False)
    )

    channel = (
        work.groupby("channel", as_index=False)
        .agg(
            transaction_count=("transaction_id", "count"),
            total_amount=("amount", "sum"),
            average_amount=("amount", "mean"),
            anomalous_transactions=("is_anomalous", "sum"),
        )
    )

    category = (
        work.groupby("merchant_category", as_index=False)
        .agg(
            transaction_count=("transaction_id", "count"),
            total_amount=("amount", "sum"),
            average_amount=("amount", "mean"),
            anomalous_transactions=("is_anomalous", "sum"),
        )
    )

    anomalies = work.loc[work["is_anomalous"] == 1].copy()
    anomalies = anomalies.sort_values("anomaly_score", ascending=False)

    kpi = pd.DataFrame(
        {
            "metric": [
                "total_transactions",
                "total_amount",
                "average_transaction_amount",
                "anomalous_transactions",
                "anomaly_rate",
                "international_transaction_rate",
            ],
            "value": [
                len(work),
                work["amount"].sum(),
                work["amount"].mean(),
                int(work["is_anomalous"].sum()),
                work["is_anomalous"].mean(),
                work["cross_border_flag"].mean(),
            ],
        }
    )
    return {"daily_kpi": daily, "country_flow": country, "channel_kpi": channel, "category_kpi": category, "anomalies": anomalies, "kpi": kpi}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-dir", default="data/gold")
    args = parser.parse_args()
    df = pd.read_csv(args.input)
    tables = build_gold(df)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    for name, table in tables.items():
        path = out / f"{name}.csv"
        table.to_csv(path, index=False)
        print(f"{name}: {len(table):,} rows -> {path}")


if __name__ == "__main__":
    main()
