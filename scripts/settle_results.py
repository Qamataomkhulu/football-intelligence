#!/usr/bin/env python3
"""
Settlement script: RESULT -> COMPARE -> CLASSIFY ERROR -> STORE -> CALIBRATE.

Reads settled prediction records (fixture result known, so each generated
selection can be marked won/lost) from data/historical/settled_predictions.json,
computes calibration buckets + Brier score + per-market hit rates, and writes
data/predictions/performance.json for the frontend's Performance page.

`data/historical/settled_predictions.json` is expected to accumulate over
time: each pipeline run's Ticket A/B selections get appended here once the
fixture has a final score (see backend/db/models.Prediction for the fuller
persisted schema once volume justifies a real database read here instead of
a flat file). This script ships with a small bundled example dataset so the
Performance page has something to render out of the box - replace it with
real settled results as they accumulate.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.calibration.calibration import (
    LossType,
    PredictionRecord,
    brier_score,
    compute_calibration,
    hit_rate_by_market,
    loss_type_breakdown,
)

SETTLED_FILE = ROOT / "data" / "historical" / "settled_predictions.json"
OUTPUT_FILE = ROOT / "data" / "predictions" / "performance.json"


def load_records() -> list[PredictionRecord]:
    if not SETTLED_FILE.exists():
        return []
    raw = json.loads(SETTLED_FILE.read_text())
    records = []
    for r in raw:
        loss_type = LossType(r["loss_type"]) if r.get("loss_type") else None
        records.append(
            PredictionRecord(
                fixture_id=r["fixture_id"],
                market_code=r["market_code"],
                model_probability=r["model_probability"],
                won=r["won"],
                loss_type=loss_type,
            )
        )
    return records


def main():
    records = load_records()
    if not records:
        print("No settled predictions yet - nothing to calibrate. "
              "Populate data/historical/settled_predictions.json as results come in.")
        output = {"n_settled": 0, "calibration": [], "brier_score": None,
                   "hit_rate_by_market": {}, "loss_type_breakdown": {}}
    else:
        output = {
            "n_settled": len(records),
            "calibration": [b.as_dict() for b in compute_calibration(records)],
            "brier_score": round(brier_score(records), 4),
            "hit_rate_by_market": hit_rate_by_market(records),
            "loss_type_breakdown": loss_type_breakdown(records),
        }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(output, indent=2))
    print(f"Wrote {OUTPUT_FILE} ({output['n_settled']} settled predictions).")


if __name__ == "__main__":
    main()
