"""
Normalization layer.

Collectors (backend/collectors/*) return raw, provider-specific JSON.
Nothing downstream should ever touch that raw shape directly - this module
is the only place that knows what a Sportmonks fixture blob or a GDELT
article list looks like, and its job is to produce the clean, provider-
agnostic dict this whole engine is built on:

    NormalizedTeamStats -> StructuralInputs / FrictionInputs
    NormalizedOdds       -> market_odds dict keyed by our market codes

Keeping this boundary strict means: if we ever add a second football data
provider, only this file changes - backend/intelligence and backend/markets
never need to know a provider exists.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Optional

from backend.intelligence.friction import FrictionInputs
from backend.intelligence.structural import StructuralInputs


@dataclass
class NormalizedTeamStats:
    """Provider-agnostic per-team stats for one fixture. Collectors +
    this module are responsible for filling this in from raw provider
    payloads; everything downstream only ever sees this shape."""

    team_id: str
    team_name: str
    is_home: bool

    # 0-1 normalized inputs feeding StructuralInputs
    first_xi_rating: float
    bench_rating: float
    form_points_per_game: float       # will be rescaled 0-1 against league avg
    home_or_away_rating: float
    tactical_fit: float
    xg_for: float
    xg_against: float
    opposition_rating: float
    europe_cup_experience: float

    # raw counts feeding FrictionInputs (normalized inside this module)
    key_injuries: int
    total_injuries: int
    suspensions: int
    days_since_last_match: int
    matches_last_14_days: int
    new_signings_in_xi: int
    transfer_saga_players: int
    days_since_manager_appointed: Optional[int]
    off_field_headlines: int


def _scale(value: float, lo: float, hi: float) -> float:
    """Linearly rescale `value` from [lo, hi] to [0, 1], clamped."""
    if hi == lo:
        return 0.5
    return max(0.0, min(1.0, (value - lo) / (hi - lo)))


def to_structural_inputs(stats: NormalizedTeamStats) -> StructuralInputs:
    xg_diff = stats.xg_for - stats.xg_against
    return StructuralInputs(
        first_xi_quality=_scale(stats.first_xi_rating, 0, 100),
        bench_quality=_scale(stats.bench_rating, 0, 100),
        current_form=_scale(stats.form_points_per_game, 0, 3),
        is_home=stats.is_home,
        home_away_strength=_scale(stats.home_or_away_rating, 0, 100),
        tactical_fit=_scale(stats.tactical_fit, 0, 100),
        xg_chance_creation=_scale(xg_diff, -2.0, 2.0),
        opposition_quality=_scale(stats.opposition_rating, 0, 100),
        europe_cup_experience=_scale(stats.europe_cup_experience, 0, 100),
    )


def to_friction_inputs(stats: NormalizedTeamStats) -> FrictionInputs:
    # Weight key injuries far more heavily than total injuries - a backup
    # left-back out is not the same as a first-choice striker out.
    injury_severity = min(1.0, stats.key_injuries * 0.3 + stats.total_injuries * 0.05)
    suspension_severity = min(1.0, stats.suspensions * 0.35)
    rotation_severity = _scale(stats.matches_last_14_days, 2, 6) * _scale(14 - stats.days_since_last_match, 0, 10)
    signings_severity = min(1.0, stats.new_signings_in_xi * 0.25)
    transfer_severity = min(1.0, stats.transfer_saga_players * 0.3)
    manager_severity = (
        _scale(60 - stats.days_since_manager_appointed, 0, 60)
        if stats.days_since_manager_appointed is not None
        else 0.0
    )
    noise_severity = min(1.0, stats.off_field_headlines * 0.15)

    return FrictionInputs(
        injuries=injury_severity,
        suspensions=suspension_severity,
        rotation_schedule=rotation_severity,
        new_signings=signings_severity,
        transfer_uncertainty=transfer_severity,
        manager_change=manager_severity,
        off_field_noise=noise_severity,
    )


def normalize_market_odds(raw_odds: dict[str, Any]) -> dict[str, float]:
    """Map provider odds keys (e.g. Sportmonks / Odds API outcome names) to
    our internal market codes from config/markets.yml. This is a thin,
    explicit mapping table on purpose - silently guessing at odds keys is
    exactly the kind of bug that would corrupt a probability model."""
    mapping = {
        "home": "WIN_HOME",
        "away": "WIN_AWAY",
        "draw": None,  # draw odds aren't a market code we price directly
        "1x": "1X",
        "x2": "X2",
        "over_1_5": "OVER_1_5",
        "over_2_5": "OVER_2_5",
        "btts_yes": "BTTS",
    }
    result = {}
    for raw_key, code in mapping.items():
        if code and raw_key in raw_odds:
            result[code] = raw_odds[raw_key]
    return result
