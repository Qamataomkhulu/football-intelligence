"""
GDELT collector - the "scrub the net" news intelligence layer.

Uses GDELT's DOC 2.0 API (no key required) to search recent global news for
per-team signal queries (injury, suspension, lineup, transfer, manager,
dressing room, contract, training). Returned articles are handed to the LLM
summarisation step (backend/intelligence/news_llm.py, not the probability
engine) to extract structured injury/transfer/tactical signals - GDELT
itself is just search, not the source of truth for scores.
"""
from __future__ import annotations

from typing import Any, Optional
from urllib.parse import quote

import requests

DOC_API_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
DEFAULT_TIMEOUT = 20

SIGNAL_QUERIES = [
    "injury",
    "suspension",
    "lineup",
    "transfer",
    "manager",
    "dressing room",
    "contract",
    "training",
]


def search_team_news(
    team_name: str, signal: str, max_records: int = 20, timespan: str = "3d"
) -> list[dict[str, Any]]:
    """Search GDELT for `"{team_name}" {signal}` and return raw article
    metadata (title, url, source, seendate, language)."""
    query = f'"{team_name}" {signal}'
    params = {
        "query": query,
        "mode": "artlist",
        "maxrecords": max_records,
        "timespan": timespan,
        "format": "json",
        "sort": "datedesc",
    }
    resp = requests.get(DOC_API_URL, params=params, timeout=DEFAULT_TIMEOUT)
    if resp.status_code != 200:
        return []
    try:
        data = resp.json()
    except ValueError:
        # GDELT occasionally returns non-JSON on empty/malformed queries
        return []
    return data.get("articles", [])


def search_team_all_signals(team_name: str, max_records_per_signal: int = 10) -> dict[str, list[dict]]:
    """Run every signal query for a team and return them grouped by signal,
    ready for the LLM summarisation step."""
    return {
        signal: search_team_news(team_name, signal, max_records=max_records_per_signal)
        for signal in SIGNAL_QUERIES
    }
