"""
Calibration & learning layer.

Every generated selection is permanently recorded (see backend/db/models.py
-> Prediction). This module compares recorded model probabilities against
actual outcomes to compute calibration buckets (e.g. "model said 70-75%,
actual hit rate was X%") and Brier score, and supports classifying losses
into the fixed taxonomy from the design doc so market-level penalties/
promotions can be derived over time.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class LossType(str, Enum):
    BAD_TEAM_EVALUATION = "bad_team_evaluation"
    WRONG_LINEUP_ASSUMPTION = "wrong_lineup_assumption"
    INJURY_OVERWEIGHTED = "injury_overweighted"
    ROTATION_UNDERESTIMATED = "rotation_underestimated"
    OPPONENT_UNDERESTIMATED = "opponent_underestimated"
    MARKET_PRICE_WRONG = "market_price_wrong"
    GOAL_MARKET_TOO_SPECIFIC = "goal_market_too_specific"
    TACTICAL_MISMATCH_MISSED = "tactical_mismatch_missed"
    GAME_STATE_ERROR = "game_state_error"
    RANDOM_VARIANCE = "random_variance"


@dataclass
class PredictionRecord:
    """Minimal shape calibration needs; backend/db/models.Prediction carries
    the full persisted record (see that module for the ORM version)."""

    fixture_id: str
    market_code: str
    model_probability: float  # 0-1
    won: bool
    loss_type: LossType | None = None


@dataclass
class CalibrationBucket:
    label: str
    low: float
    high: float
    n: int
    wins: int

    @property
    def predicted_midpoint(self) -> float:
        return (self.low + self.high) / 2

    @property
    def actual_hit_rate(self) -> float:
        return self.wins / self.n if self.n else 0.0

    def as_dict(self) -> dict:
        return {
            "bucket": self.label,
            "n": self.n,
            "predicted_midpoint": round(self.predicted_midpoint, 3),
            "actual_hit_rate": round(self.actual_hit_rate, 3),
            "calibration_error": round(self.actual_hit_rate - self.predicted_midpoint, 3),
        }


DEFAULT_BUCKETS = [
    (0.50, 0.60, "50-60%"),
    (0.60, 0.70, "60-70%"),
    (0.70, 0.75, "70-75%"),
    (0.75, 0.85, "75-85%"),
    (0.85, 1.01, "85-100%"),
]


def compute_calibration(records: list[PredictionRecord]) -> list[CalibrationBucket]:
    buckets = []
    for low, high, label in DEFAULT_BUCKETS:
        in_bucket = [r for r in records if low <= r.model_probability < high]
        wins = sum(1 for r in in_bucket if r.won)
        buckets.append(CalibrationBucket(label=label, low=low, high=high, n=len(in_bucket), wins=wins))
    return buckets


def brier_score(records: list[PredictionRecord]) -> float:
    """Mean squared error between predicted probability and outcome (0/1).
    Lower is better; 0 = perfect, 0.25 = coin-flip-level uninformative."""
    if not records:
        return 0.0
    total = sum((r.model_probability - (1.0 if r.won else 0.0)) ** 2 for r in records)
    return total / len(records)


def hit_rate_by_market(records: list[PredictionRecord]) -> dict[str, dict]:
    """Per-market hit rate, used to promote/penalise specific market codes
    over time (e.g. demote TEAM_SCORE_BOTH_HALVES if it keeps underhitting,
    per the design doc's post-mortem)."""
    by_market: dict[str, list[PredictionRecord]] = {}
    for r in records:
        by_market.setdefault(r.market_code, []).append(r)

    out = {}
    for market_code, recs in by_market.items():
        n = len(recs)
        wins = sum(1 for r in recs if r.won)
        out[market_code] = {
            "n": n,
            "wins": wins,
            "hit_rate": round(wins / n, 3) if n else 0.0,
            "avg_model_probability": round(sum(r.model_probability for r in recs) / n, 3) if n else 0.0,
        }
    return out


def loss_type_breakdown(records: list[PredictionRecord]) -> dict[str, int]:
    losses = [r for r in records if not r.won and r.loss_type]
    out: dict[str, int] = {}
    for r in losses:
        out[r.loss_type.value] = out.get(r.loss_type.value, 0) + 1
    return out
