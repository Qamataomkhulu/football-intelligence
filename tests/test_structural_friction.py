from backend.intelligence.structural import StructuralInputs, calculate_structural_score
from backend.intelligence.friction import FrictionInputs, calculate_friction_score


def test_structural_score_max_when_all_inputs_perfect():
    inputs = StructuralInputs(
        first_xi_quality=1.0,
        bench_quality=1.0,
        current_form=1.0,
        is_home=True,
        home_away_strength=1.0,
        tactical_fit=1.0,
        xg_chance_creation=1.0,
        opposition_quality=1.0,
        europe_cup_experience=1.0,
    )
    result = calculate_structural_score(inputs)
    assert result.total == result.max_total == 90
    assert result.pct == 100.0


def test_structural_score_zero_when_all_inputs_zero():
    inputs = StructuralInputs(
        first_xi_quality=0, bench_quality=0, current_form=0, is_home=True,
        home_away_strength=0, tactical_fit=0, xg_chance_creation=0,
        opposition_quality=0, europe_cup_experience=0,
    )
    result = calculate_structural_score(inputs)
    assert result.total == 0
    assert result.pct == 0.0


def test_structural_score_clamps_out_of_range_inputs():
    inputs = StructuralInputs(
        first_xi_quality=5.0,  # way above 1.0
        bench_quality=-3.0,    # way below 0.0
        current_form=0.5, is_home=True, home_away_strength=0.5,
        tactical_fit=0.5, xg_chance_creation=0.5, opposition_quality=0.5,
        europe_cup_experience=0.5,
    )
    result = calculate_structural_score(inputs)
    assert result.first_xi_quality == 20  # clamped to max
    assert result.bench_quality == 0      # clamped to min


def test_friction_score_off_field_noise_has_smallest_weight():
    """Regression test for the design doc's explicit philosophy: off-field
    rumours must never be able to outweigh injuries or manager change."""
    noise_only = FrictionInputs(
        injuries=0, suspensions=0, rotation_schedule=0, new_signings=0,
        transfer_uncertainty=0, manager_change=0, off_field_noise=1.0,
    )
    injuries_only = FrictionInputs(
        injuries=1.0, suspensions=0, rotation_schedule=0, new_signings=0,
        transfer_uncertainty=0, manager_change=0, off_field_noise=0,
    )
    noise_result = calculate_friction_score(noise_only)
    injury_result = calculate_friction_score(injuries_only)
    assert noise_result.total < injury_result.total


def test_friction_score_max_is_25():
    inputs = FrictionInputs(
        injuries=1, suspensions=1, rotation_schedule=1, new_signings=1,
        transfer_uncertainty=1, manager_change=1, off_field_noise=1,
    )
    result = calculate_friction_score(inputs)
    assert result.total == result.max_total == 25
