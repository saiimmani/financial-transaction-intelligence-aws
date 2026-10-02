import json
from pathlib import Path

from src.anomaly.detector import attach_anomaly_scores, evaluate
from src.data_generator import generate_transactions
from src.analytics.gold_tables import build_gold


def test_generator_is_reproducible():
    a = generate_transactions(1000, 42)
    b = generate_transactions(1000, 42)
    assert a.equals(b)
    assert int(a["ground_truth_anomaly"].sum()) > 0


def test_detector_produces_expected_columns():
    df = generate_transactions(1500, 42)
    scored = attach_anomaly_scores(df)
    for column in ["anomaly_score", "anomaly_flag", "anomaly_severity", "anomaly_reason"]:
        assert column in scored.columns
    assert scored["anomaly_score"].between(0, 100).all()
    assert scored["anomaly_flag"].sum() > 0


def test_model_evaluation_available():
    scored = attach_anomaly_scores(generate_transactions(2000, 42))
    metrics = evaluate(scored)
    assert metrics["available"] is True
    assert 0 <= metrics["roc_auc"] <= 1
    assert metrics["support"] > 0


def test_gold_tables_exist():
    scored = attach_anomaly_scores(generate_transactions(1500, 42))
    tables = build_gold(scored)
    for name in ["daily_kpi", "country_flow", "channel_kpi", "category_kpi", "anomalies", "kpi"]:
        assert name in tables
        assert len(tables[name]) > 0
