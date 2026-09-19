from backend.calibration.calibration import (
    LossType,
    PredictionRecord,
    brier_score,
    compute_calibration,
    hit_rate_by_market,
    loss_type_breakdown,
)


def _records():
    return [
        PredictionRecord("f1", "1X", 0.74, True),
        PredictionRecord("f2", "1X", 0.67, False, LossType.INJURY_OVERWEIGHTED),
        PredictionRecord("f3", "BTTS_OVER_2_5", 0.72, False, LossType.GOAL_MARKET_TOO_SPECIFIC),
        PredictionRecord("f4", "1X", 0.71, True),
    ]


def test_compute_calibration_buckets_correctly():
    buckets = compute_calibration(_records())
    bucket_70_75 = next(b for b in buckets if b.label == "70-75%")
    assert bucket_70_75.n == 3
    assert bucket_70_75.wins == 2


def test_brier_score_perfect_prediction_is_zero():
    perfect = [PredictionRecord("f1", "1X", 1.0, True), PredictionRecord("f2", "1X", 0.0, False)]
    assert brier_score(perfect) == 0.0


def test_brier_score_worst_case_is_one():
    worst = [PredictionRecord("f1", "1X", 1.0, False)]
    assert brier_score(worst) == 1.0


def test_hit_rate_by_market():
    rates = hit_rate_by_market(_records())
    assert rates["1X"]["n"] == 3
    assert rates["1X"]["wins"] == 2
    assert rates["BTTS_OVER_2_5"]["hit_rate"] == 0.0


def test_loss_type_breakdown_counts_only_losses_with_a_type():
    breakdown = loss_type_breakdown(_records())
    assert breakdown["injury_overweighted"] == 1
    assert breakdown["goal_market_too_specific"] == 1
    assert sum(breakdown.values()) == 2
