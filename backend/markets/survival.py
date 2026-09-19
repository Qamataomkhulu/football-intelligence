"""
Market Survival engine.

Given expected goals for both teams (Poisson lambdas derived from the power
ratings), build a joint scoreline probability grid and use it to price
every candidate market in config/markets.yml. Then compare each market's
model probability to its market-implied probability to find:

    Which market best expresses the edge while surviving plausible
    match outcomes?

This is what stops Ticket B from picking a thesis-correct-but-overly-specific
market (e.g. the "Rennes X2 + O1.5" failure mode described in the design
doc): a market only "survives" if MODEL_PROB / MARKET_IMPLIED_PROB clears
the configured minimum ratio (config/weights.yml -> market_survival.min_ratio).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from backend.intelligence.config_loader import get_markets, get_weights

MAX_GOALS = 10  # grid truncation; P(>=10 goals) is negligible for football


def _poisson_pmf(k: int, lam: float) -> float:
    return math.exp(-lam) * lam**k / math.factorial(k)


def build_goal_grid(lambda_home: float, lambda_away: float) -> list[list[float]]:
    """Independent-Poisson joint grid: grid[h][a] = P(home scores h, away scores a).

    NOTE: this assumes independence between the two teams' scoring, which
    slightly overprices low-scoring draws (0-0, 1-1) relative to reality.
    A Dixon-Coles low-score correction factor (tau) is a natural v2
    improvement; flagged here rather than silently baked in.
    """
    home_pmf = [_poisson_pmf(h, lambda_home) for h in range(MAX_GOALS + 1)]
    away_pmf = [_poisson_pmf(a, lambda_away) for a in range(MAX_GOALS + 1)]
    return [[h * a for a in away_pmf] for h in home_pmf]


@dataclass
class GoalModel:
    lambda_home: float
    lambda_away: float
    grid: list[list[float]]

    @classmethod
    def from_lambdas(cls, lambda_home: float, lambda_away: float) -> "GoalModel":
        return cls(lambda_home, lambda_away, build_goal_grid(lambda_home, lambda_away))

    def p_home_win(self) -> float:
        return sum(self.grid[h][a] for h in range(MAX_GOALS + 1) for a in range(MAX_GOALS + 1) if h > a)

    def p_draw(self) -> float:
        return sum(self.grid[i][i] for i in range(MAX_GOALS + 1))

    def p_away_win(self) -> float:
        return sum(self.grid[h][a] for h in range(MAX_GOALS + 1) for a in range(MAX_GOALS + 1) if h < a)

    def p_over(self, line: float) -> float:
        return sum(
            self.grid[h][a]
            for h in range(MAX_GOALS + 1)
            for a in range(MAX_GOALS + 1)
            if h + a > line
        )

    def p_btts(self) -> float:
        return sum(
            self.grid[h][a] for h in range(1, MAX_GOALS + 1) for a in range(1, MAX_GOALS + 1)
        )

    def p_team_over(self, team: str, line: float) -> float:
        if team == "home":
            return sum(self._home_marginal()[h] for h in range(MAX_GOALS + 1) if h > line)
        return sum(self._away_marginal()[a] for a in range(MAX_GOALS + 1) if a > line)

    def p_home_handicap_plus(self, handicap: float) -> float:
        # Home team +handicap "survives" if home_goals - away_goals + handicap > 0
        return sum(
            self.grid[h][a]
            for h in range(MAX_GOALS + 1)
            for a in range(MAX_GOALS + 1)
            if (h - a) + handicap > 0
        )

    def p_away_handicap_plus(self, handicap: float) -> float:
        return sum(
            self.grid[h][a]
            for h in range(MAX_GOALS + 1)
            for a in range(MAX_GOALS + 1)
            if (a - h) + handicap > 0
        )

    def _home_marginal(self) -> list[float]:
        return [sum(row) for row in self.grid]

    def _away_marginal(self) -> list[float]:
        return [sum(self.grid[h][a] for h in range(MAX_GOALS + 1)) for a in range(MAX_GOALS + 1)]

    def p_team_score_both_halves(self, team: str) -> float:
        """Approximation: split each team's expected goals evenly across
        halves and treat each half as an independent Poisson(lambda/2).
        Real half-by-half xG data (when available from the collector) should
        replace this approximation."""
        lam = self.lambda_home if team == "home" else self.lambda_away
        half_lambda = lam / 2
        p_score_in_half = 1 - _poisson_pmf(0, half_lambda)
        return p_score_in_half * p_score_in_half

    def p_ht_ft(self, ht_result: str, ft_result: str) -> float:
        """Very rough HT/FT approximation using the half-split assumption
        above; treats each half as an independent mini-match with half the
        expected goals. Marked approximate - a real half-time xG feed from
        the collector should replace this in v2."""
        half_home, half_away = self.lambda_home / 2, self.lambda_away / 2
        ht_grid = build_goal_grid(half_home, half_away)
        second_half_grid = build_goal_grid(self.lambda_home / 2, self.lambda_away / 2)

        def result_prob(grid, result):
            if result == "H":
                return sum(grid[h][a] for h in range(MAX_GOALS + 1) for a in range(MAX_GOALS + 1) if h > a)
            if result == "A":
                return sum(grid[h][a] for h in range(MAX_GOALS + 1) for a in range(MAX_GOALS + 1) if h < a)
            return sum(grid[i][i] for i in range(MAX_GOALS + 1))

        # Treat halves as independent for this approximation.
        return result_prob(ht_grid, ht_result) * result_prob(second_half_grid, ft_result)


def price_market(model: GoalModel, market_code: str) -> Optional[float]:
    """Return the model probability for a given market code, or None if the
    market code is unrecognised."""
    if market_code == "WIN_HOME":
        return model.p_home_win()
    if market_code == "WIN_AWAY":
        return model.p_away_win()
    if market_code == "DNB_HOME":
        h, d, a = model.p_home_win(), model.p_draw(), model.p_away_win()
        return h / (h + a) if (h + a) else 0.0
    if market_code == "DNB_AWAY":
        h, d, a = model.p_home_win(), model.p_draw(), model.p_away_win()
        return a / (h + a) if (h + a) else 0.0
    if market_code == "1X":
        return model.p_home_win() + model.p_draw()
    if market_code == "X2":
        return model.p_away_win() + model.p_draw()
    if market_code == "HOME_PLUS_0_5":
        return model.p_home_handicap_plus(0.5)
    if market_code == "AWAY_PLUS_0_5":
        return model.p_away_handicap_plus(0.5)
    if market_code == "HOME_PLUS_1_5":
        return model.p_home_handicap_plus(1.5)
    if market_code == "AWAY_PLUS_1_5":
        return model.p_away_handicap_plus(1.5)
    if market_code == "OVER_1_5":
        return model.p_over(1.5)
    if market_code == "OVER_2_5":
        return model.p_over(2.5)
    if market_code == "BTTS":
        return model.p_btts()
    if market_code == "BTTS_OVER_2_5":
        # approx: joint prob from grid directly (not independence-multiplied)
        return sum(
            model.grid[h][a]
            for h in range(1, MAX_GOALS + 1)
            for a in range(1, MAX_GOALS + 1)
            if h + a > 2.5
        )
    if market_code == "WIN_OVER_1_5":
        return sum(
            model.grid[h][a]
            for h in range(MAX_GOALS + 1)
            for a in range(MAX_GOALS + 1)
            if h != a and h + a > 1.5
        )
    if market_code == "WIN_BTTS":
        return sum(
            model.grid[h][a]
            for h in range(1, MAX_GOALS + 1)
            for a in range(1, MAX_GOALS + 1)
            if h != a
        )
    if market_code == "TEAM_OVER_1_5":
        # priced per-team by caller (see price_team_market); default to home
        return model.p_team_over("home", 1.5)
    if market_code == "TEAM_SCORE_BOTH_HALVES":
        return model.p_team_score_both_halves("home")
    if market_code == "HT_FT":
        return model.p_ht_ft("H", "H")
    return None


@dataclass
class MarketSurvivalResult:
    market_code: str
    label: str
    model_probability: float
    market_implied_probability: Optional[float]
    ratio: Optional[float]  # model_probability / market_implied_probability

    def as_dict(self) -> dict:
        return {
            "market_code": self.market_code,
            "label": self.label,
            "model_probability": round(self.model_probability, 4),
            "market_implied_probability": (
                round(self.market_implied_probability, 4)
                if self.market_implied_probability is not None
                else None
            ),
            "ratio": round(self.ratio, 3) if self.ratio is not None else None,
        }


def evaluate_all_markets(
    model: GoalModel, market_odds: dict[str, float]
) -> list[MarketSurvivalResult]:
    """
    market_odds: mapping of market_code -> decimal odds (already de-vigged /
    best-available), as sourced from backend/collectors/odds_api.py.
    Markets with no odds available are still priced (model_probability) but
    get ratio=None so they can be shown without being ranked.
    """
    results = []
    for market in get_markets():
        code = market["code"]
        model_prob = price_market(model, code)
        if model_prob is None:
            continue
        odds = market_odds.get(code)
        implied = (1 / odds) if odds else None
        ratio = (model_prob / implied) if implied else None
        results.append(
            MarketSurvivalResult(
                market_code=code,
                label=market["label"],
                model_probability=model_prob,
                market_implied_probability=implied,
                ratio=ratio,
            )
        )
    return results


def best_surviving_market(
    results: list[MarketSurvivalResult], min_ratio: Optional[float] = None
) -> Optional[MarketSurvivalResult]:
    """Pick the market with the highest MODEL_PROB / MARKET_IMPLIED_PROB
    ratio, subject to a minimum ratio threshold from config."""
    threshold = min_ratio if min_ratio is not None else get_weights()["market_survival"]["min_ratio"]
    candidates = [r for r in results if r.ratio is not None and r.ratio >= threshold]
    if not candidates:
        return None
    return max(candidates, key=lambda r: r.ratio)
