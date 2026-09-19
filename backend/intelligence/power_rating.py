"""
Combines Structural (0-90) and Friction (0-25) into a single 0-100 power
rating per team, then converts a pair of power ratings into a match
probability distribution (home win / draw / away win) using a logistic
model calibrated against historical results.

This is deliberately simple and auditable rather than a black box: the
whole point of the engine is that every number on the site can be traced
back to an equation, not an LLM guess.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from backend.intelligence.config_loader import get_weights
from backend.intelligence.structural import StructuralBreakdown
from backend.intelligence.friction import FrictionBreakdown


@dataclass
class PowerRating:
    structural_pct: float   # 0-100
    friction_pct: float     # 0-100, higher = MORE friction (worse)
    rating: float           # 0-100 combined

    def as_dict(self) -> dict:
        return {
            "structural_pct": round(self.structural_pct, 1),
            "friction_pct": round(self.friction_pct, 1),
            "rating": round(self.rating, 1),
        }


def calculate_power_rating(
    structural: StructuralBreakdown, friction: FrictionBreakdown
) -> PowerRating:
    combine = get_weights()["combine"]
    structural_pct = 100 * structural.total / structural.max_total
    friction_pct = 100 * friction.total / friction.max_total  # higher = worse

    rating = (
        structural_pct * combine["structural_share"]
        + (100 - friction_pct) * combine["friction_share"]
    )
    return PowerRating(structural_pct=structural_pct, friction_pct=friction_pct, rating=rating)


@dataclass
class MatchProbabilities:
    home_win: float
    draw: float
    away_win: float

    def as_dict(self) -> dict:
        return {
            "home_win": round(self.home_win, 4),
            "draw": round(self.draw, 4),
            "away_win": round(self.away_win, 4),
        }


def ratings_to_probabilities(
    home_rating: float,
    away_rating: float,
    home_advantage: float = 6.0,
    draw_base: float = 0.24,
    scale: float = 14.0,
) -> MatchProbabilities:
    """
    Logistic conversion from power-rating gap to a home/draw/away
    distribution.

    - `home_advantage` shifts the effective home rating up (points on the
      0-100 scale) to reflect the generic home-field effect.
    - `draw_base` sets the baseline draw probability before adjusting for
      how close the match is; closer matches draw more often.
    - `scale` controls how sharply rating gaps translate into win probability
      (smaller = gaps matter more).

    These three constants are the model's only "hyperparameters" and should
    be re-fit periodically against backend/calibration results.
    """
    gap = (home_rating + home_advantage) - away_rating

    # Base win-probability-before-draw-adjustment via logistic function.
    p_home_before_draw = 1 / (1 + math.exp(-gap / scale))

    # Draw probability shrinks as the gap widens (blowouts draw less).
    draw = draw_base * math.exp(-abs(gap) / (scale * 2.2))

    p_home = p_home_before_draw * (1 - draw)
    p_away = (1 - p_home_before_draw) * (1 - draw)

    total = p_home + draw + p_away
    return MatchProbabilities(home_win=p_home / total, draw=draw / total, away_win=p_away / total)


def estimate_expected_goals(
    home_rating: float,
    away_rating: float,
    league_avg_goals_per_team: float = 1.35,
    home_advantage_goals: float = 0.22,
    rating_to_goals: float = 55.0,
) -> tuple[float, float]:
    """
    Convert a pair of 0-100 power ratings into expected goals (Poisson
    lambdas) for each side. This is a simple, auditable linear mapping
    around a league-average baseline rather than a fitted Dixon-Coles model.

    `rating_to_goals` controls how many rating points correspond to one
    extra expected goal; re-fit this against backend/calibration data as
    results accumulate.
    """
    gap = home_rating - away_rating
    home_lambda = max(0.15, league_avg_goals_per_team + home_advantage_goals + gap / rating_to_goals)
    away_lambda = max(0.15, league_avg_goals_per_team - home_advantage_goals - gap / rating_to_goals)
    return home_lambda, away_lambda
