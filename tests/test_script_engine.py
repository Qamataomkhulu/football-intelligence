from backend.intelligence.script import derive_ticket_c
from backend.markets.survival import GoalModel


def test_ticket_c_only_refines_within_the_map_for_1x():
    model = GoalModel.from_lambdas(1.7, 0.9)
    odds = {
        "1X": 1.7,             # underpriced -> Ticket B picks this
        "HOME_PLUS_1_5": 1.25,
        "OVER_1_5": 1.4,
        "BTTS_OVER_2_5": 2.4,
        "TEAM_OVER_1_5": 2.0,
        "HOME_PLUS_0_5": 1.6,
    }
    result = derive_ticket_c("1X", model, odds, min_ratio=1.05)
    assert result.ticket_b_market == "1X"
    if result.ticket_c_market is not None:
        from backend.intelligence.script import REFINEMENT_MAP
        assert result.ticket_c_market in REFINEMENT_MAP["1X"]


def test_ticket_c_falls_back_to_ticket_b_when_nothing_survives():
    model = GoalModel.from_lambdas(1.35, 1.35)
    fair_1x = 1 / (model.p_home_win() + model.p_draw())
    odds = {"1X": fair_1x}  # fairly priced -> no refinement should clear threshold
    result = derive_ticket_c("1X", model, odds, min_ratio=1.5)
    assert result.ticket_c_market is None
    assert result.ticket_c_result is None


def test_derive_ticket_c_raises_on_unpriced_market():
    model = GoalModel.from_lambdas(1.5, 1.2)
    import pytest
    with __import__("pytest").raises(ValueError):
        derive_ticket_c("NOT_A_REAL_MARKET", model, {}, min_ratio=1.05)
