from backend.markets.survival import (
    GoalModel,
    best_surviving_market,
    evaluate_all_markets,
    price_market,
)


def test_goal_grid_probabilities_sum_to_one():
    model = GoalModel.from_lambdas(1.5, 1.1)
    total = sum(sum(row) for row in model.grid)
    assert abs(total - 1.0) < 1e-6


def test_home_draw_away_probabilities_sum_to_one():
    model = GoalModel.from_lambdas(1.8, 0.9)
    total = model.p_home_win() + model.p_draw() + model.p_away_win()
    # Small tolerance for grid truncation at MAX_GOALS.
    assert abs(total - 1.0) < 1e-5


def test_stronger_home_team_has_higher_win_probability():
    strong_home = GoalModel.from_lambdas(2.2, 0.8)
    even_match = GoalModel.from_lambdas(1.35, 1.35)
    assert strong_home.p_home_win() > even_match.p_home_win()


def test_double_chance_equals_win_plus_draw():
    model = GoalModel.from_lambdas(1.6, 1.2)
    one_x = price_market(model, "1X")
    assert abs(one_x - (model.p_home_win() + model.p_draw())) < 1e-9


def test_btts_probability_is_between_zero_and_one():
    model = GoalModel.from_lambdas(1.6, 1.3)
    btts = price_market(model, "BTTS")
    assert 0 < btts < 1


def test_best_surviving_market_respects_min_ratio():
    model = GoalModel.from_lambdas(2.0, 0.7)
    # Deliberately underpriced 1X to create a large surviving ratio.
    odds = {"WIN_HOME": 1.9, "1X": 3.0, "OVER_1_5": 1.5}
    results = evaluate_all_markets(model, odds)
    best = best_surviving_market(results, min_ratio=1.05)
    assert best is not None
    assert best.ratio >= 1.05


def test_best_surviving_market_returns_none_when_nothing_clears_threshold():
    model = GoalModel.from_lambdas(1.35, 1.35)
    # Odds priced exactly at model probability -> ratio ~1.0, below any
    # reasonable minimum threshold.
    fair_home = 1 / model.p_home_win()
    results = evaluate_all_markets(model, {"WIN_HOME": fair_home})
    best = best_surviving_market(results, min_ratio=1.2)
    assert best is None
