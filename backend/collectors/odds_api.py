"""
The Odds API collector (https://the-odds-api.com), used as a SECOND odds
source alongside Sportmonks' own odds include, so we can store best/average/
worst prices and bookmaker counts rather than trusting a single book.

Requires ODDS_API_KEY in the environment.
"""
from __future__ import annotations

import os
import statistics
from dataclasses import dataclass
from typing import Any, Optional

import requests

BASE_URL = "https://api.the-odds-api.com/v4"
DEFAULT_TIMEOUT = 20


class OddsApiError(RuntimeError):
    pass


def _api_key() -> str:
    key = os.environ.get("ODDS_API_KEY")
    if not key:
        raise OddsApiError(
            "ODDS_API_KEY is not set. Add it to your environment or GitHub "
            "Actions secrets - never commit it to the repo."
        )
    return key


def get_odds(
    sport_key: str,
    regions: str = "uk,eu",
    markets: str = "h2h,spreads,totals",
    odds_format: str = "decimal",
) -> list[dict[str, Any]]:
    params = {
        "apiKey": _api_key(),
        "regions": regions,
        "markets": markets,
        "oddsFormat": odds_format,
    }
    resp = requests.get(f"{BASE_URL}/sports/{sport_key}/odds", params=params, timeout=DEFAULT_TIMEOUT)
    if resp.status_code != 200:
        raise OddsApiError(f"Odds API returned {resp.status_code}: {resp.text[:300]}")
    return resp.json()


def get_sports() -> list[dict[str, Any]]:
    resp = requests.get(f"{BASE_URL}/sports", params={"apiKey": _api_key()}, timeout=DEFAULT_TIMEOUT)
    if resp.status_code != 200:
        raise OddsApiError(f"Odds API returned {resp.status_code}: {resp.text[:300]}")
    return resp.json()


@dataclass
class AggregatedOdds:
    outcome: str
    best_odds: float
    average_odds: float
    worst_odds: float
    market_movement: Optional[float]  # % change vs a previous snapshot, if supplied
    bookmaker_count: int

    def as_dict(self) -> dict:
        return {
            "outcome": self.outcome,
            "best_odds": round(self.best_odds, 3),
            "average_odds": round(self.average_odds, 3),
            "worst_odds": round(self.worst_odds, 3),
            "market_movement": round(self.market_movement, 3) if self.market_movement is not None else None,
            "bookmaker_count": self.bookmaker_count,
        }


def aggregate_h2h_odds(
    event: dict[str, Any], previous_best: Optional[dict[str, float]] = None
) -> dict[str, AggregatedOdds]:
    """Collapse a raw Odds API event (many bookmakers) into best/average/
    worst per outcome, matching the storage shape the design doc calls for:
    best_odds, average_odds, worst_odds, market_movement, bookmaker_count."""
    by_outcome: dict[str, list[float]] = {}
    for bookmaker in event.get("bookmakers", []):
        for market in bookmaker.get("markets", []):
            if market.get("key") != "h2h":
                continue
            for outcome in market.get("outcomes", []):
                by_outcome.setdefault(outcome["name"], []).append(outcome["price"])

    result = {}
    for outcome, prices in by_outcome.items():
        best = max(prices)
        movement = None
        if previous_best and outcome in previous_best and previous_best[outcome]:
            movement = 100 * (best - previous_best[outcome]) / previous_best[outcome]
        result[outcome] = AggregatedOdds(
            outcome=outcome,
            best_odds=best,
            average_odds=statistics.mean(prices),
            worst_odds=min(prices),
            market_movement=movement,
            bookmaker_count=len(prices),
        )
    return result
