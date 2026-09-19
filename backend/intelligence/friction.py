"""
Friction score: a 0-25 deterministic penalty capturing everything that could
degrade a team's structural quality on matchday - injuries, suspensions,
rotation risk, new signings bedding in, manager change, and off-field noise.

Deliberately small weight on off_field_noise (max 2/25): a headline like
"player unhappy" should not outweigh a team having a superior XI, bench,
xG trend and tactical matchup. See config/weights.yml.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from backend.intelligence.config_loader import get_weights


@dataclass
class FrictionInputs:
    """Normalized 0-1 inputs, each representing severity (1 = worst)."""

    injuries: float              # weighted by starter importance, not just count
    suspensions: float
    rotation_schedule: float     # fixture congestion / travel burden
    new_signings: float          # integration risk of recent arrivals in the XI
    transfer_uncertainty: float  # unsettled players linked with exits
    manager_change: float        # recency of managerial appointment
    off_field_noise: float       # dressing room / boardroom rumours - low weight by design


@dataclass
class FrictionBreakdown:
    injuries: float
    suspensions: float
    rotation_schedule: float
    new_signings: float
    transfer_uncertainty: float
    manager_change: float
    off_field_noise: float
    total: float
    max_total: float = field(default=25.0)

    def as_dict(self) -> dict:
        return {
            "injuries": round(self.injuries, 2),
            "suspensions": round(self.suspensions, 2),
            "rotation_schedule": round(self.rotation_schedule, 2),
            "new_signings": round(self.new_signings, 2),
            "transfer_uncertainty": round(self.transfer_uncertainty, 2),
            "manager_change": round(self.manager_change, 2),
            "off_field_noise": round(self.off_field_noise, 2),
            "total": round(self.total, 2),
            "max_total": self.max_total,
        }


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def calculate_friction_score(inputs: FrictionInputs) -> FrictionBreakdown:
    w = get_weights()["friction"]

    injuries = _clamp01(inputs.injuries) * w["injuries"]["max"]
    suspensions = _clamp01(inputs.suspensions) * w["suspensions"]["max"]
    rotation = _clamp01(inputs.rotation_schedule) * w["rotation_schedule"]["max"]
    signings = _clamp01(inputs.new_signings) * w["new_signings"]["max"]
    transfer = _clamp01(inputs.transfer_uncertainty) * w["transfer_uncertainty"]["max"]
    manager = _clamp01(inputs.manager_change) * w["manager_change"]["max"]
    noise = _clamp01(inputs.off_field_noise) * w["off_field_noise"]["max"]

    max_total = sum(v["max"] for v in w.values())
    total = injuries + suspensions + rotation + signings + transfer + manager + noise

    return FrictionBreakdown(
        injuries=injuries,
        suspensions=suspensions,
        rotation_schedule=rotation,
        new_signings=signings,
        transfer_uncertainty=transfer,
        manager_change=manager,
        off_field_noise=noise,
        total=total,
        max_total=max_total,
    )
