"""
Ticket generator.

Ties the whole pipeline together for a single fixture:

  structural + friction -> power rating -> expected goals -> goal model
      -> consensus gap (vs market) -> market survival -> best market
      -> (Ticket B edge) -> match script engine -> Ticket C refinement

Per the design doc's key architectural decision, market choice is
DOWNSTREAM of the football analysis: the code never starts by asking
"who wins" and then bolting a market onto the answer. It starts by
measuring disagreement (consensus gap), then asks which market best
survives that disagreement.

Ticket A = strongest evidence-to-risk selections (structural favourites,
           market roughly agrees, low friction).
Ticket B = consensus breaker: cases where our model disagrees materially
           with the market and a market exists that expresses that edge.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from backend.intelligence.config_loader import get_weights
from backend.intelligence.consensus import ConsensusGap, calculate_consensus_gap
from backend.intelligence.friction import FrictionBreakdown
from backend.intelligence.power_rating import PowerRating
from backend.intelligence.script import MatchScriptResult, derive_ticket_c
from backend.intelligence.structural import StructuralBreakdown
from backend.markets.survival import GoalModel, best_surviving_market, evaluate_all_markets


@dataclass
class FixtureAnalysis:
    fixture_id: str
    home_team: str
    away_team: str
    home_structural: StructuralBreakdown
    away_structural: StructuralBreakdown
    home_friction: FrictionBreakdown
    away_friction: FrictionBreakdown
    home_power: PowerRating
    away_power: PowerRating
    goal_model: GoalModel
    market_odds: dict[str, float]
    reasons_home: list[str] = field(default_factory=list)
    reasons_away: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)


@dataclass
class TicketSelection:
    fixture_id: str
    home_team: str
    away_team: str
    ticket: str                       # "A" or "B"
    market_code: str
    label: str
    model_probability: float
    market_implied_probability: Optional[float]
    edge_ratio: Optional[float]
    consensus_gap_pp: float
    trap_score: float                 # 0-100 composite confidence score
    reasons: list[str]
    risks: list[str]
    ticket_c: Optional[MatchScriptResult] = None

    def as_dict(self) -> dict:
        return {
            "fixture_id": self.fixture_id,
            "match": f"{self.home_team} vs {self.away_team}",
            "ticket": self.ticket,
            "market_code": self.market_code,
            "label": self.label,
            "model_probability": round(self.model_probability, 4),
            "market_implied_probability": (
                round(self.market_implied_probability, 4)
                if self.market_implied_probability is not None
                else None
            ),
            "edge_ratio": round(self.edge_ratio, 3) if self.edge_ratio is not None else None,
            "consensus_gap_pp": round(self.consensus_gap_pp, 2),
            "trap_score": round(self.trap_score, 1),
            "reasons": self.reasons,
            "risks": self.risks,
            "ticket_c": self.ticket_c.as_dict() if self.ticket_c else None,
        }


def _trap_score(edge_ratio: Optional[float], consensus_gap_pp: float, friction_penalty: float) -> float:
    """Composite 0-100 confidence score shown on the intelligence page.

    Blends: how much the market mispriced the outcome (edge ratio), how
    large the raw consensus gap is, and how much friction risk remains.
    This is a presentation/ranking aid, not a probability - the actual
    stake decision should always be made from model_probability and
    market_implied_probability.
    """
    ratio_component = min(40.0, (edge_ratio - 1) * 100) if edge_ratio else 0.0
    gap_component = min(40.0, abs(consensus_gap_pp) * 1.5)
    friction_component = max(0.0, 20.0 - friction_penalty * 0.8)
    return max(0.0, min(100.0, ratio_component + gap_component + friction_component))


def generate_ticket_a_selection(analysis: FixtureAnalysis) -> Optional[TicketSelection]:
    """Ticket A: structural value. Pick the outcome our model rates highest
    among WIN_HOME / WIN_AWAY / 1X / X2, and only keep it if the market
    roughly agrees (small-to-moderate consensus gap) with low remaining
    friction - i.e. a "safe" structural favourite, not a contrarian pick."""
    weights = get_weights()
    results = {r.market_code: r for r in evaluate_all_markets(analysis.goal_model, analysis.market_odds)}

    best = None
    for code in ("WIN_HOME", "WIN_AWAY", "1X", "X2"):
        r = results.get(code)
        if r is None or r.market_implied_probability is None:
            continue
        gap = calculate_consensus_gap(code, r.model_probability, r.market_implied_probability)
        if abs(gap.gap_pp) < weights["consensus"]["min_gap_ticket_a"]:
            continue
        if best is None or (r.ratio or 0) > (best[0].ratio or 0):
            best = (r, gap)

    if best is None:
        return None
    r, gap = best
    friction_penalty = (analysis.home_friction.total + analysis.away_friction.total) / 2
    trap = _trap_score(r.ratio, gap.gap_pp, friction_penalty)
    return TicketSelection(
        fixture_id=analysis.fixture_id,
        home_team=analysis.home_team,
        away_team=analysis.away_team,
        ticket="A",
        market_code=r.market_code,
        label=r.label,
        model_probability=r.model_probability,
        market_implied_probability=r.market_implied_probability,
        edge_ratio=r.ratio,
        consensus_gap_pp=gap.gap_pp,
        trap_score=trap,
        reasons=analysis.reasons_home if gap.gap_pp >= 0 else analysis.reasons_away,
        risks=analysis.risks,
    )


def generate_ticket_b_selection(analysis: FixtureAnalysis) -> Optional[TicketSelection]:
    """Ticket B: consensus breaker. Find the market with the largest gap
    between model and market AND the best surviving ratio - this is the
    validated philosophy the whole platform is built around."""
    weights = get_weights()
    results = evaluate_all_markets(analysis.goal_model, analysis.market_odds)
    best = best_surviving_market(results, min_ratio=weights["market_survival"]["min_ratio"])
    if best is None or best.market_implied_probability is None:
        return None

    gap = calculate_consensus_gap(best.market_code, best.model_probability, best.market_implied_probability)
    if abs(gap.gap_pp) < weights["consensus"]["min_gap_ticket_b"]:
        return None

    ticket_c = derive_ticket_c(
        best.market_code, analysis.goal_model, analysis.market_odds, weights["market_survival"]["min_ratio"]
    )

    friction_penalty = (analysis.home_friction.total + analysis.away_friction.total) / 2
    trap = _trap_score(best.ratio, gap.gap_pp, friction_penalty)

    reasons = analysis.reasons_home if best.market_code in ("WIN_HOME", "1X", "DNB_HOME", "HOME_PLUS_0_5", "HOME_PLUS_1_5") else analysis.reasons_away

    return TicketSelection(
        fixture_id=analysis.fixture_id,
        home_team=analysis.home_team,
        away_team=analysis.away_team,
        ticket="B",
        market_code=best.market_code,
        label=best.label,
        model_probability=best.model_probability,
        market_implied_probability=best.market_implied_probability,
        edge_ratio=best.ratio,
        consensus_gap_pp=gap.gap_pp,
        trap_score=trap,
        reasons=reasons,
        risks=analysis.risks,
        ticket_c=ticket_c,
    )


def build_tickets(analyses: list[FixtureAnalysis]) -> dict:
    """Run Ticket A and Ticket B generation across all analysed fixtures and
    return the structure the API/dashboard consumes."""
    ticket_a, ticket_b = [], []
    for analysis in analyses:
        a = generate_ticket_a_selection(analysis)
        if a:
            ticket_a.append(a)
        b = generate_ticket_b_selection(analysis)
        if b:
            ticket_b.append(b)

    ticket_a.sort(key=lambda s: s.trap_score, reverse=True)
    ticket_b.sort(key=lambda s: s.trap_score, reverse=True)

    def combined_odds(selections: list[TicketSelection]) -> Optional[float]:
        if not selections or any(s.market_implied_probability in (None, 0) for s in selections):
            return None
        product = 1.0
        for s in selections:
            product *= 1 / s.market_implied_probability
        return round(product, 2)

    return {
        "ticket_a": {
            "selections": [s.as_dict() for s in ticket_a],
            "target_odds": combined_odds(ticket_a),
        },
        "ticket_b": {
            "selections": [s.as_dict() for s in ticket_b],
            "target_odds": combined_odds(ticket_b),
        },
    }
