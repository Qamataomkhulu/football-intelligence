"""
Structural score: a 0-90 deterministic rating of a team's footballing quality
for a specific fixture, built from normalized inputs (not vibes, not LLM
opinion). See config/weights.yml for the sub-score ceilings.

Every function here is pure and unit-testable: given the same normalized
inputs, it always returns the same score. Nothing here calls an LLM or an
API - that happens upstream in backend/collectors and
backend/normalizers.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from backend.intelligence.config_loader import get_weights


@dataclass
class StructuralInputs:
    """Normalized, 0-1 scaled inputs for one team in one fixture.

    Each field is expected to already be normalized (0 = worst plausible,
    1 = best plausible) by backend/normalizers before it reaches this model.
    """

    first_xi_quality: float        # e.g. sum of player ratings / squad benchmark
    bench_quality: float           # depth + quality of available substitutes
    current_form: float            # points-per-game over last N matches, normalized
    is_home: bool
    home_away_strength: float      # team's home or away split rating, normalized
    tactical_fit: float            # matchup-specific tactical suitability score
    xg_chance_creation: float      # xG for / against trend, normalized
    opposition_quality: float      # strength of opponent (drags score down if weak fixture list)
    europe_cup_experience: float   # squad's continental/cup-run experience, normalized


@dataclass
class StructuralBreakdown:
    first_xi_quality: float
    bench_quality: float
    current_form: float
    home_away: float
    tactical_fit: float
    xg_chance_creation: float
    opposition_quality: float
    europe_cup_experience: float
    total: float
    max_total: float = field(default=90.0)

    @property
    def pct(self) -> float:
        return round(100 * self.total / self.max_total, 1) if self.max_total else 0.0

    def as_dict(self) -> dict:
        return {
            "first_xi_quality": round(self.first_xi_quality, 2),
            "bench_quality": round(self.bench_quality, 2),
            "current_form": round(self.current_form, 2),
            "home_away": round(self.home_away, 2),
            "tactical_fit": round(self.tactical_fit, 2),
            "xg_chance_creation": round(self.xg_chance_creation, 2),
            "opposition_quality": round(self.opposition_quality, 2),
            "europe_cup_experience": round(self.europe_cup_experience, 2),
            "total": round(self.total, 2),
            "max_total": self.max_total,
            "pct": self.pct,
        }


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def calculate_structural_score(inputs: StructuralInputs) -> StructuralBreakdown:
    w = get_weights()["structural"]

    first_xi = _clamp01(inputs.first_xi_quality) * w["first_xi_quality"]["max"]
    bench = _clamp01(inputs.bench_quality) * w["bench_quality"]["max"]
    form = _clamp01(inputs.current_form) * w["current_form"]["max"]
    home_away = _clamp01(inputs.home_away_strength) * w["home_away"]["max"]
    tactical = _clamp01(inputs.tactical_fit) * w["tactical_fit"]["max"]
    xg = _clamp01(inputs.xg_chance_creation) * w["xg_chance_creation"]["max"]
    opp_quality = _clamp01(inputs.opposition_quality) * w["opposition_quality"]["max"]
    europe = _clamp01(inputs.europe_cup_experience) * w["europe_cup_experience"]["max"]

    max_total = sum(v["max"] for v in w.values())
    total = first_xi + bench + form + home_away + tactical + xg + opp_quality + europe

    return StructuralBreakdown(
        first_xi_quality=first_xi,
        bench_quality=bench,
        current_form=form,
        home_away=home_away,
        tactical_fit=tactical,
        xg_chance_creation=xg,
        opposition_quality=opp_quality,
        europe_cup_experience=europe,
        total=total,
        max_total=max_total,
    )
