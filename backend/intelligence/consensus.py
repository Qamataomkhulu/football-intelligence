"""
Consensus Gap engine.

The core question the whole platform is built around:

    Where is the disagreement between current football evidence
    and market expectation?

This module takes our model's probability for an outcome and the market's
implied probability (from de-vigged odds) and returns the gap, in both
percentage-point and ratio form. It does NOT pick a market - that is the
job of backend/markets/survival.py. This module only measures disagreement.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class ConsensusGap:
    outcome: str                 # e.g. "HOME_WIN", "1X", "AWAY_WIN"
    model_probability: float     # 0-1
    market_probability: float    # 0-1, de-vigged implied probability
    gap_pp: float                # model - market, in percentage points
    edge_ratio: float            # model_probability / market_probability

    @property
    def direction(self) -> str:
        if self.gap_pp > 0:
            return "market_underpriced"   # our model is more confident than the market
        if self.gap_pp < 0:
            return "market_overpriced"    # market is more confident than our model
        return "aligned"

    def as_dict(self) -> dict:
        return {
            "outcome": self.outcome,
            "model_probability": round(self.model_probability, 4),
            "market_probability": round(self.market_probability, 4),
            "gap_pp": round(self.gap_pp, 2),
            "edge_ratio": round(self.edge_ratio, 3),
            "direction": self.direction,
        }


def devig_two_way(odds_a: float, odds_b: float) -> tuple[float, float]:
    """De-vig a two-way market (e.g. DNB, BTTS Y/N) using proportional method."""
    imp_a, imp_b = 1 / odds_a, 1 / odds_b
    overround = imp_a + imp_b
    return imp_a / overround, imp_b / overround


def devig_three_way(odds_home: float, odds_draw: float, odds_away: float) -> tuple[float, float, float]:
    """De-vig a three-way 1X2 market using proportional (basic) method."""
    imp_h, imp_d, imp_a = 1 / odds_home, 1 / odds_draw, 1 / odds_away
    overround = imp_h + imp_d + imp_a
    return imp_h / overround, imp_d / overround, imp_a / overround


def calculate_consensus_gap(
    outcome: str, model_probability: float, market_probability: float
) -> ConsensusGap:
    gap_pp = (model_probability - market_probability) * 100
    edge_ratio = model_probability / market_probability if market_probability else float("inf")
    return ConsensusGap(
        outcome=outcome,
        model_probability=model_probability,
        market_probability=market_probability,
        gap_pp=gap_pp,
        edge_ratio=edge_ratio,
    )


def rank_gaps(gaps: list[ConsensusGap], min_gap_pp: Optional[float] = None) -> list[ConsensusGap]:
    """Return gaps sorted by absolute size, optionally filtered by a minimum
    percentage-point threshold (used to gate Ticket A / Ticket B eligibility)."""
    filtered = [g for g in gaps if min_gap_pp is None or abs(g.gap_pp) >= min_gap_pp]
    return sorted(filtered, key=lambda g: abs(g.gap_pp), reverse=True)
