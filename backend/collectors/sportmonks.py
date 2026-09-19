"""
Sportmonks collector.

Wraps the Sportmonks Football API (fixtures, form, H2H, xG, statistics,
lineups, injuries, odds, predictions, transfers, news - all reachable via
the fixture endpoint with `include` params). Requires SPORTMONKS_API_KEY in
the environment; never hardcode the key or commit it.

This module intentionally does NOT parse Sportmonks' response shape into
our internal fixture model - that's backend/normalizers/normalize.py's job.
Collectors only fetch and return raw JSON so the two layers can be tested
independently.
"""
from __future__ import annotations

import os
from typing import Any, Optional

import requests

BASE_URL = "https://api.sportmonks.com/v3/football"
DEFAULT_TIMEOUT = 20


class SportmonksError(RuntimeError):
    pass


def _api_key() -> str:
    key = os.environ.get("SPORTMONKS_API_KEY")
    if not key:
        raise SportmonksError(
            "SPORTMONKS_API_KEY is not set. Add it to your environment or "
            "GitHub Actions secrets - never commit it to the repo."
        )
    return key


def _get(path: str, params: Optional[dict] = None) -> dict[str, Any]:
    params = dict(params or {})
    params["api_token"] = _api_key()
    resp = requests.get(f"{BASE_URL}{path}", params=params, timeout=DEFAULT_TIMEOUT)
    if resp.status_code != 200:
        raise SportmonksError(f"Sportmonks {path} returned {resp.status_code}: {resp.text[:300]}")
    return resp.json()


def get_fixtures_by_date(date: str, league_ids: Optional[list[int]] = None) -> dict:
    """date format: YYYY-MM-DD."""
    params = {
        "include": (
            "participants;league;venue;state;"
            "scores;lineups;statistics;"
            "xGFixture;odds;predictions;"
            "trends;weatherReport"
        )
    }
    if league_ids:
        params["filters"] = f"fixtureLeagues:{','.join(map(str, league_ids))}"
    return _get(f"/fixtures/date/{date}", params=params)


def get_fixture(fixture_id: int) -> dict:
    params = {
        "include": (
            "participants;league;venue;"
            "lineups.player;statistics;"
            "xGFixture;odds;predictions;"
            "sidelined;trends;metadata"
        )
    }
    return _get(f"/fixtures/{fixture_id}", params=params)


def get_team_form(team_id: int, last_n: int = 6) -> dict:
    params = {"include": "form", "per_page": last_n}
    return _get(f"/teams/{team_id}", params=params)


def get_head_to_head(team_a_id: int, team_b_id: int) -> dict:
    return _get(f"/fixtures/head-to-head/{team_a_id}/{team_b_id}")


def get_injuries(team_id: int) -> dict:
    return _get(f"/sidelined/teams/{team_id}")


def get_transfer_rumours(team_id: int) -> dict:
    return _get(f"/transfers/teams/{team_id}")


def get_news(team_id: Optional[int] = None) -> dict:
    params = {"filters": f"newsTeamId:{team_id}"} if team_id else None
    return _get("/news/pre-match", params=params)


def get_leagues() -> dict:
    """Used to populate config/leagues.yml sportmonks_id fields."""
    return _get("/leagues")
