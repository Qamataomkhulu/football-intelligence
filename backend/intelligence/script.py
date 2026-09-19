"""
Match Script engine.

Per the design doc, Ticket C must NOT independently scan the world - it is
derived FROM the edge side that Ticket B already identified:

    TICKET B ENGINE -> IDENTIFY EDGE SIDE -> MATCH SCRIPT ENGINE
        -> GOALS / HALVES / RESULT -> refined market (Ticket C)

This module takes the edge side (e.g. "Brentford 1X") plus the underlying
structural/friction reasons for that edge, and asks the Market Survival
engine whether a more specific - but still surviving - market exists that
better expresses the same thesis (e.g. "Brentford 1X + O1.5" only if that
combo still clears the survival ratio; otherwise it stays at "Brentford 1X").
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from backend.markets.survival import GoalModel, evaluate_all_markets, MarketSurvivalResult


# Which refined markets are plausible follow-ons for a given Ticket B edge
# market. This encodes "goals / halves / result" branches from the design
# doc without letting the script engine wander into unrelated markets.
REFINEMENT_MAP: dict[str, list[str]] = {
    "1X": ["HOME_PLUS_0_5", "HOME_PLUS_1_5", "OVER_1_5", "BTTS_OVER_2_5", "TEAM_OVER_1_5"],
    "X2": ["AWAY_PLUS_0_5", "AWAY_PLUS_1_5", "OVER_1_5", "BTTS_OVER_2_5", "TEAM_OVER_1_5"],
    "WIN_HOME": ["WIN_OVER_1_5", "WIN_BTTS", "HOME_PLUS_1_5", "TEAM_SCORE_BOTH_HALVES", "HT_FT"],
    "WIN_AWAY": ["WIN_OVER_1_5", "WIN_BTTS", "AWAY_PLUS_1_5", "TEAM_SCORE_BOTH_HALVES", "HT_FT"],
    "DNB_HOME": ["HOME_PLUS_1_5", "WIN_OVER_1_5", "TEAM_OVER_1_5"],
    "DNB_AWAY": ["AWAY_PLUS_1_5", "WIN_OVER_1_5", "TEAM_OVER_1_5"],
}


@dataclass
class MatchScriptResult:
    ticket_b_market: str
    ticket_c_market: Optional[str]
    reason: str
    ticket_b_result: MarketSurvivalResult
    ticket_c_result: Optional[MarketSurvivalResult]

    def as_dict(self) -> dict:
        return {
            "ticket_b_market": self.ticket_b_market,
            "ticket_c_market": self.ticket_c_market,
            "reason": self.reason,
            "ticket_b": self.ticket_b_result.as_dict(),
            "ticket_c": self.ticket_c_result.as_dict() if self.ticket_c_result else None,
        }


def derive_ticket_c(
    ticket_b_market_code: str,
    goal_model: GoalModel,
    market_odds: dict[str, float],
    min_ratio: float,
) -> MatchScriptResult:
    """Given the Ticket B edge market, try each plausible refinement and keep
    the one with the strongest surviving ratio - never a market outside
    REFINEMENT_MAP for that edge, and never one that fails the survival
    threshold (in which case Ticket C simply equals Ticket B - no forced
    over-specification)."""
    all_results = {r.market_code: r for r in evaluate_all_markets(goal_model, market_odds)}
    ticket_b_result = all_results.get(ticket_b_market_code)
    if ticket_b_result is None:
        raise ValueError(f"Unknown or unpriced Ticket B market: {ticket_b_market_code}")

    candidates = REFINEMENT_MAP.get(ticket_b_market_code, [])
    surviving = [
        all_results[c]
        for c in candidates
        if c in all_results and all_results[c].ratio is not None and all_results[c].ratio >= min_ratio
    ]

    if not surviving:
        return MatchScriptResult(
            ticket_b_market=ticket_b_market_code,
            ticket_c_market=None,
            reason=(
                "No refinement of the Ticket B edge survives the minimum ratio "
                f"threshold ({min_ratio}); Ticket C stays at the Ticket B market "
                "to avoid an overly-specific goal-market penalty."
            ),
            ticket_b_result=ticket_b_result,
            ticket_c_result=None,
        )

    best = max(surviving, key=lambda r: r.ratio)
    return MatchScriptResult(
        ticket_b_market=ticket_b_market_code,
        ticket_c_market=best.market_code,
        reason=(
            f"'{best.label}' extends the Ticket B thesis with the strongest "
            f"surviving ratio ({best.ratio}) among plausible goal/half/result "
            "refinements."
        ),
        ticket_b_result=ticket_b_result,
        ticket_c_result=best,
    )
