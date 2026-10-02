"""One-command local demonstration of the complete analytics workflow."""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.anomaly.detector import attach_anomaly_scores, evaluate
from src.data_generator import generate_transactions
from src.analytics.gold_tables import build_gold


def main() -> None:
    out = ROOT / "data" / "demo"
    out.mkdir(parents=True, exist_ok=True)

    raw = generate_transactions(rows=20000, seed=42)
    raw_path = out / "transactions_raw.csv"
    raw.to_csv(raw_path, index=False)

    scored = attach_anomaly_scores(raw)
    scored_path = out / "transactions_scored.csv"
    scored.to_csv(scored_path, index=False)

    metrics = evaluate(scored)
    (out / "model_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    for name, table in build_gold(scored).items():
        table.to_csv(out / f"{name}.csv", index=False)

    print("\n=== Financial Transaction Analytics Demo ===")
    print(f"Raw transactions : {len(raw):,}")
    print(f"Detected anomalies: {int(scored['anomaly_flag'].sum()):,}")
    print(f"Gold tables       : {len(build_gold(scored))}")
    if metrics.get("available"):
        print(f"ROC-AUC           : {metrics['roc_auc']:.4f}")
        print(f"Precision          : {metrics['precision']:.4f}")
        print(f"Recall             : {metrics['recall']:.4f}")
        print(f"F1                 : {metrics['f1']:.4f}")
    print(f"Output directory  : {out}")


if __name__ == "__main__":
    main()
