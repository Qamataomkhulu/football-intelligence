"""Small cached YAML config loader shared by the intelligence layer."""
from __future__ import annotations

import functools
from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


@functools.lru_cache(maxsize=None)
def _load_yaml(name: str) -> dict:
    path = CONFIG_DIR / name
    with open(path, "r") as f:
        return yaml.safe_load(f)


def get_weights() -> dict:
    return _load_yaml("weights.yml")


def get_markets() -> list[dict]:
    return _load_yaml("markets.yml")["markets"]


def get_leagues() -> dict:
    return _load_yaml("leagues.yml")


def clear_cache() -> None:
    """Used by tests that monkeypatch config files."""
    _load_yaml.cache_clear()
