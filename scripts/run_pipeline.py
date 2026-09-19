#!/usr/bin/env python3
"""
Pipeline orchestrator.

Implements the flow from the design doc:

    Scrape/ingest -> normalize -> analyse -> identify consensus gaps
        -> calculate match scripts -> select markets -> generate tickets

By default this reads data/sample/fixtures.json (already-normalized shape)
so the whole pipeline can be demonstrated and tested with zero API keys.
Pass --live to instead pull fixtures/odds/injuries from Sportmonks + The
Odds API + GDELT for a given date (requires SPORTMONKS_API_KEY and
ODDS_API_KEY in the environment).

Output: data/predictions/latest.json - the single file the FastAPI backend
serves to the frontend dashboard.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.intelligence.friction import calculate_friction_score
from backend.intelligence.power_rating import calculate_power_rating, estimate_expected_goals
from backend.intelligence.structural import calculate_structural_score
from backend.markets.survival import GoalModel
from backend.normalizers.normalize import (
    NormalizedTeamStats,
    to_friction_inputs,
    to_structural_inputs,
)
from backend.tickets.generator import FixtureAnalysis, build_tickets

DATA_DIR = ROOT / "data" / "predictions"


def _team_stats_from_json(d: dict, is_home: bool) -> NormalizedTeamStats:
    return NormalizedTeamStats(
        team_id=d["team_id"],
        team_name=d["team_name"],
        is_home=is_home,
        first_xi_rating=d["first_xi_rating"],
        bench_rating=d["bench_rating"],
        form_points_per_game=d["form_points_per_game"],
        home_or_away_rating=d["home_or_away_rating"],
        tactical_fit=d["tactical_fit"],
        xg_for=d["xg_for"],
        xg_against=d["xg_against"],
        opposition_rating=d["opposition_rating"],
        europe_cup_experience=d["europe_cup_experience"],
        key_injuries=d["key_injuries"],
        total_injuries=d["total_injuries"],
        suspensions=d["suspensions"],
        days_since_last_match=d["days_since_last_match"],
        matches_last_14_days=d["matches_last_14_days"],
        new_signings_in_xi=d["new_signings_in_xi"],
        transfer_saga_players=d["transfer_saga_players"],
        days_since_manager_appointed=d.get("days_since_manager_appointed"),
        off_field_headlines=d["off_field_headlines"],
    )


def _build_reasons(stats: NormalizedTeamStats, structural_pct: float, friction_total: float) -> list[str]:
    reasons = []
    if structural_pct >= 65:
        reasons.append(f"{stats.team_name} structural rating is strong ({structural_pct:.0f}%).")
    if stats.xg_for - stats.xg_against > 0.4:
        reasons.append(f"{stats.team_name} positive xG trend ({stats.xg_for:.2f} for vs {stats.xg_against:.2f} against).")
    if stats.form_points_per_game >= 1.8:
        reasons.append(f"{stats.team_name} strong recent form ({stats.form_points_per_game:.1f} pts/game).")
    if friction_total <= 5:
        reasons.append(f"{stats.team_name} low friction - clean bill of health.")
    return reasons


def _build_risks(stats: NormalizedTeamStats, friction_total: float) -> list[str]:
    risks = []
    if stats.key_injuries > 0:
        risks.append(f"{stats.team_name}: {stats.key_injuries} key injury absence(s).")
    if stats.matches_last_14_days >= 4:
        risks.append(f"{stats.team_name}: fixture congestion ({stats.matches_last_14_days} matches in 14 days).")
    if stats.days_since_manager_appointed is not None and stats.days_since_manager_appointed < 30:
        risks.append(f"{stats.team_name}: new manager, tactical settling risk.")
    if friction_total >= 10:
        risks.append(f"{stats.team_name}: elevated overall friction ({friction_total:.1f}/25).")
    return risks


def analyse_fixture(raw: dict) -> FixtureAnalysis:
    home_stats = _team_stats_from_json(raw["home"], is_home=True)
    away_stats = _team_stats_from_json(raw["away"], is_home=False)

    home_structural = calculate_structural_score(to_structural_inputs(home_stats))
    away_structural = calculate_structural_score(to_structural_inputs(away_stats))
    home_friction = calculate_friction_score(to_friction_inputs(home_stats))
    away_friction = calculate_friction_score(to_friction_inputs(away_stats))

    home_power = calculate_power_rating(home_structural, home_friction)
    away_power = calculate_power_rating(away_structural, away_friction)

    lambda_home, lambda_away = estimate_expected_goals(home_power.rating, away_power.rating)
    goal_model = GoalModel.from_lambdas(lambda_home, lambda_away)

    return FixtureAnalysis(
        fixture_id=raw["fixture_id"],
        home_team=home_stats.team_name,
        away_team=away_stats.team_name,
        home_structural=home_structural,
        away_structural=away_structural,
        home_friction=home_friction,
        away_friction=away_friction,
        home_power=home_power,
        away_power=away_power,
        goal_model=goal_model,
        market_odds=raw["market_odds"],
        reasons_home=_build_reasons(home_stats, home_power.structural_pct, home_friction.total),
        reasons_away=_build_reasons(away_stats, away_power.structural_pct, away_friction.total),
        risks=_build_risks(home_stats, home_friction.total) + _build_risks(away_stats, away_friction.total),
    )


def fixture_detail_dict(analysis: FixtureAnalysis) -> dict:
    from backend.markets.survival import evaluate_all_markets

    market_results = evaluate_all_markets(analysis.goal_model, analysis.market_odds)
    return {
        "fixture_id": analysis.fixture_id,
        "home_team": analysis.home_team,
        "away_team": analysis.away_team,
        "home_power_rating": analysis.home_power.as_dict(),
        "away_power_rating": analysis.away_power.as_dict(),
        "home_structural": analysis.home_structural.as_dict(),
        "away_structural": analysis.away_structural.as_dict(),
        "home_friction": analysis.home_friction.as_dict(),
        "away_friction": analysis.away_friction.as_dict(),
        "expected_goals": {
            "home": round(analysis.goal_model.lambda_home, 2),
            "away": round(analysis.goal_model.lambda_away, 2),
        },
        "markets": [m.as_dict() for m in market_results],
        "reasons_home": analysis.reasons_home,
        "reasons_away": analysis.reasons_away,
        "risks": analysis.risks,
    }


def run(input_path: Path, output_path: Path) -> dict:
    raw_fixtures = json.loads(input_path.read_text())
    analyses = [analyse_fixture(f) for f in raw_fixtures]
    tickets = build_tickets(analyses)

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "matches_scanned": len(raw_fixtures),
            "matches_analysed": len(analyses),
            "ticket_a_count": len(tickets["ticket_a"]["selections"]),
            "ticket_b_count": len(tickets["ticket_b"]["selections"]),
        },
        "tickets": tickets,
        "fixtures": [fixture_detail_dict(a) for a in analyses],
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2))
    return output


def main():
    parser = argparse.ArgumentParser(description="Run the football intelligence pipeline.")
    parser.add_argument(
        "--input",
        type=Path,
        default=ROOT / "data" / "sample" / "fixtures.json",
        help="Path to normalized fixtures JSON (default: bundled sample data).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DATA_DIR / "latest.json",
        help="Where to write the pipeline output (default: data/predictions/latest.json).",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="(Not yet wired up) Pull live data from Sportmonks/Odds API/GDELT instead of sample data.",
    )
    args = parser.parse_args()

    if args.live:
        raise SystemExit(
            "Live mode requires SPORTMONKS_API_KEY / ODDS_API_KEY and a "
            "collector->normalizer wiring pass for your Sportmonks plan's "
            "exact response shape - see backend/collectors/sportmonks.py "
            "and backend/normalizers/normalize.py. Run without --live to "
            "use the bundled sample data."
        )

    output = run(args.input, args.output)
    print(
        f"Pipeline complete: {output['summary']['matches_analysed']} fixtures analysed, "
        f"{output['summary']['ticket_a_count']} Ticket A selections, "
        f"{output['summary']['ticket_b_count']} Ticket B selections."
    )
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
