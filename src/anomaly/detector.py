"""Explainable + ML anomaly detection for synthetic financial transactions.

The local model is intentionally unsupervised: the planted ground-truth label in the
synthetic generator is ONLY used for evaluation, never as a model feature.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import IsolationForest
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

REQUIRED_COLUMNS = [
    "transaction_id",
    "transaction_timestamp",
    "customer_id",
    "sender_account",
    "receiver_account",
    "sender_country",
    "receiver_country",
    "currency",
    "amount",
    "transaction_type",
    "merchant_category",
    "channel",
    "device_type",
]


@dataclass(frozen=True)
class DetectorConfig:
    contamination: float = 0.03
    random_state: int = 42
    anomaly_threshold: float = 50.0


def validate_input(df: pd.DataFrame) -> None:
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")


def _add_velocity(df: pd.DataFrame) -> pd.Series:
    """Count prior transactions from the same sender in the preceding 60 minutes.

    The current transaction is excluded from the count.
    """
    result = pd.Series(0, index=df.index, dtype="int64")
    ordered = df.sort_values(["sender_account", "transaction_timestamp"])
    for _, group in ordered.groupby("sender_account", sort=False):
        ts = group["transaction_timestamp"].astype("int64") // 10**9
        vals = ts.to_numpy()
        counts = np.empty(len(vals), dtype=np.int64)
        left = 0
        for i, current in enumerate(vals):
            while left < i and current - vals[left] > 3600:
                left += 1
            counts[i] = i - left
        result.loc[group.index] = counts
    return result


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    validate_input(df)
    work = df.copy()
    work["transaction_timestamp"] = pd.to_datetime(work["transaction_timestamp"], utc=True)
    work["amount"] = pd.to_numeric(work["amount"], errors="coerce")
    work = work.dropna(subset=["transaction_id", "transaction_timestamp", "amount"]).copy()
    work = work[work["amount"] > 0].copy()

    sender_median = work.groupby("sender_account")["amount"].transform("median")
    abs_dev = (work["amount"] - sender_median).abs()
    mad = abs_dev.groupby(work["sender_account"]).transform("median")
    work["sender_robust_zscore"] = (0.6745 * (work["amount"] - sender_median) / mad.replace(0, np.nan)).fillna(0).abs()

    work["velocity_1h"] = _add_velocity(work)
    work["cross_border_flag"] = (work["sender_country"] != work["receiver_country"]).astype(int)
    work["amount_log"] = np.log1p(work["amount"])
    work["hour"] = work["transaction_timestamp"].dt.hour
    work["is_weekend"] = (work["transaction_timestamp"].dt.dayofweek >= 5).astype(int)

    # High-value is defined relative to the current batch rather than a hard-coded currency value.
    high_value_cutoff = float(work["amount"].quantile(0.995))
    work["high_value_flag"] = (work["amount"] >= high_value_cutoff).astype(int)

    # Explainable risk score. It is deliberately transparent and deterministic.
    work["rule_anomaly_score"] = (
        np.minimum(work["sender_robust_zscore"] / 10.0, 1.0) * 35.0
        + np.minimum(work["velocity_1h"] / 10.0, 1.0) * 25.0
        + work["cross_border_flag"] * 15.0
        + work["high_value_flag"] * 25.0
    ).round(2)
    return work


def _ml_score(df: pd.DataFrame, config: DetectorConfig) -> np.ndarray:
    numeric = [
        "amount_log",
        "sender_robust_zscore",
        "velocity_1h",
        "cross_border_flag",
        "high_value_flag",
        "hour",
        "is_weekend",
    ]
    categorical = ["transaction_type", "merchant_category", "channel", "device_type"]

    pre = ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), numeric),
            ("cat", OneHotEncoder(handle_unknown="ignore"), categorical),
        ]
    )
    model = IsolationForest(
        n_estimators=300,
        contamination=config.contamination,
        random_state=config.random_state,
        n_jobs=-1,
    )
    pipe = Pipeline([("preprocess", pre), ("model", model)])
    pipe.fit(df[numeric + categorical])

    decision = pipe.decision_function(df[numeric + categorical])
    # IsolationForest decision values: lower means more abnormal. Map to 0..100.
    return np.clip((0.5 - decision) * 100.0, 0.0, 100.0)


def attach_anomaly_scores(df: pd.DataFrame, config: DetectorConfig | None = None) -> pd.DataFrame:
    config = config or DetectorConfig()
    features = engineer_features(df)
    features["ml_anomaly_score"] = np.round(_ml_score(features, config), 2)
    features["anomaly_score"] = np.round(
        0.60 * features["rule_anomaly_score"] + 0.40 * features["ml_anomaly_score"], 2
    )
    features["anomaly_flag"] = (features["anomaly_score"] >= config.anomaly_threshold).astype(int)
    features["anomaly_severity"] = pd.cut(
        features["anomaly_score"],
        bins=[-np.inf, 25, 50, 75, np.inf],
        labels=["LOW", "MEDIUM", "HIGH", "CRITICAL"],
        right=False,
    ).astype(str)

    def reason(row: pd.Series) -> str:
        reasons: list[str] = []
        if row["sender_robust_zscore"] >= 3:
            reasons.append("UNUSUAL_AMOUNT")
        if row["velocity_1h"] >= 6:
            reasons.append("HIGH_VELOCITY")
        if row["cross_border_flag"] == 1:
            reasons.append("CROSS_BORDER")
        if row["high_value_flag"] == 1:
            reasons.append("HIGH_VALUE")
        return "|".join(reasons) if reasons else "MODEL_SIGNAL"

    features["anomaly_reason"] = features.apply(reason, axis=1)
    return features


def evaluate(df: pd.DataFrame) -> dict:
    """Evaluate against synthetic ground truth if the column is present."""
    if "ground_truth_anomaly" not in df.columns:
        return {"available": False}

    y_true = df["ground_truth_anomaly"].astype(int)
    y_pred = df["anomaly_flag"].astype(int)
    score = df["anomaly_score"].astype(float)
    report = classification_report(y_true, y_pred, output_dict=True, zero_division=0)
    try:
        auc = float(roc_auc_score(y_true, score))
    except ValueError:
        auc = None
    return {
        "available": True,
        "roc_auc": auc,
        "precision": float(report["1"]["precision"]),
        "recall": float(report["1"]["recall"]),
        "f1": float(report["1"]["f1-score"]),
        "support": int(y_true.sum()),
        "flagged": int(y_pred.sum()),
    }
