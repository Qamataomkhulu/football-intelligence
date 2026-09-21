# Football Intelligence Engine

An explainable football intelligence engine — not a tipster website.

The platform reproduces a manual analysis workflow end to end:

```
Scrape/ingest → normalize → analyse → identify consensus gaps
    → calculate match scripts → select markets → generate tickets
    → track results → learn from misses
```

**The core architectural rule:** market selection is *downstream* of the
football analysis, never the reverse. The engine never starts by asking
"who wins" — it starts by asking:

> Where is the disagreement between current football evidence and market
> expectation?

Two tickets come out the other end:

- **Ticket A — Structural Value**: the strongest evidence-to-risk selections,
  where the model and market broadly agree.
- **Ticket B — Consensus Breaker**: fixtures where the model disagrees
  materially with the market, expressed through whichever market *survives*
  that disagreement (not the most specific market that happens to fit a
  narrative — see [Market Survival](#market-survival--ticket-c) below).

Every number on the site traces back to an equation, not a vibe. An LLM is
only ever used for news summarisation and narrative explanation — **never**
to calculate a probability.

## Quickstart (no API keys required)

The repo ships with sample fixture data so you can see the entire pipeline
run end to end immediately.

```bash
# 1. Backend
cd backend
pip install -r requirements.txt
cd ..
python scripts/run_pipeline.py          # writes data/predictions/latest.json
python scripts/settle_results.py        # writes data/predictions/performance.json

# 2. Run the API (optional - the frontend can also read the JSON directly)
uvicorn backend.api.main:app --reload

# 3. Frontend
cd frontend
npm install
npm run dev                             # http://localhost:3000
```

Run the test suite:

```bash
pip install -r backend/requirements.txt
pytest tests/ -v
```

## Architecture

```
football-intelligence/
├── frontend/                # Next.js + TypeScript dashboard
│   └── app/                 # dashboard, /fixtures/[id], /performance
├── backend/
│   ├── api/                 # FastAPI - thin read layer over pipeline JSON
│   ├── collectors/          # Sportmonks, The Odds API, GDELT clients
│   ├── normalizers/         # provider JSON -> internal normalized schema
│   ├── intelligence/        # structural/friction/consensus/power-rating/
│   │                         # match-script - the deterministic core
│   ├── markets/             # Poisson goal-grid + market survival engine
│   ├── tickets/             # Ticket A / Ticket B generator
│   ├── calibration/         # Brier score, hit-rate buckets, loss taxonomy
│   └── db/                  # SQLAlchemy models (Postgres in prod, SQLite locally)
├── data/
│   ├── sample/               # bundled demo fixtures (no API keys needed)
│   ├── historical/           # settled predictions used for calibration
│   └── predictions/          # pipeline output JSON (latest.json, performance.json)
├── scripts/
│   ├── run_pipeline.py       # ingest -> normalize -> analyse -> tickets
│   └── settle_results.py     # result -> compare -> classify -> calibrate
├── config/
│   ├── weights.yml            # structural/friction weights, thresholds
│   ├── markets.yml            # candidate market list
│   └── leagues.yml            # MVP league scope
├── tests/                    # 25 unit tests over the intelligence layer
└── .github/workflows/        # collect.yml / analyse.yml / settle.yml
```

## The scoring model

**Structural score (0–90)** — footballing quality for this fixture:
First XI quality, bench quality, current form, home/away split, tactical
fit, xG/chance creation, opposition quality, European/cup experience.

**Friction score (0–25)** — matchday risk that degrades structural quality:
injuries, suspensions, rotation/schedule, new signings, transfer
uncertainty, manager change, off-field noise.

Off-field noise is deliberately capped at the smallest weight (2/25). A
headline like *"player unhappy"* should never outweigh a team having a
superior XI, bench, xG trend, and tactical matchup — this is enforced by a
regression test (`tests/test_structural_friction.py`).

Structural + Friction combine into a single 0–100 **power rating** per team
(`backend/intelligence/power_rating.py`), which is converted into expected
goals (Poisson lambdas) for both sides.

## Consensus gap

```
Chelsea WIN market = 67%    Chelsea WIN model = 49%   → gap = −18pp
Brentford 1X market = 58%   Brentford 1X model = 77%  → edge = +19pp
```

`backend/intelligence/consensus.py` de-vigs market odds and measures the
gap between model and market probability for every outcome. This measures
*disagreement* — it does not pick a market.

## Market survival & Ticket C

A goal-scoreline probability grid (`backend/markets/survival.py`) built from
each team's expected goals prices all 19 candidate markets in
`config/markets.yml` (WIN, DNB, 1X/X2, ±handicaps, over/under, BTTS,
combos, team totals, both-halves, HT/FT). Each market's

```
MODEL_PROBABILITY / MARKET_IMPLIED_PROBABILITY
```

ratio determines whether it "survives." This is what prevents the
over-specification failure mode from the design doc's post-mortem (e.g.
"Rennes X2 + O1.5" — a correct thesis killed by an unnecessary condition).

Ticket C is never generated independently. `backend/intelligence/script.py`
takes Ticket B's edge market and only considers a fixed, market-specific
refinement map (goals / halves / result branches) — if nothing in that map
clears the survival threshold, Ticket C simply equals Ticket B.

## Calibration & learning

Every generated selection is meant to be permanently recorded
(`backend/db/models.py::Prediction`, mirrored to
`data/historical/settled_predictions.json` as a flat-file interim store).
`scripts/settle_results.py` computes:

- Calibration buckets (e.g. "model said 70–75%, actual hit rate was X%")
- Brier score
- Per-market hit rate (to promote/demote specific markets over time)
- Loss-type breakdown, using a fixed taxonomy: bad team evaluation, wrong
  lineup assumption, injury overweighted, rotation underestimated, opponent
  underestimated, market price wrong, goal market too specific, tactical
  mismatch missed, game-state error, random variance.

## Data sources

| Source | Purpose | Key required |
|---|---|---|
| [Sportmonks](https://www.sportmonks.com/) | fixtures, form, H2H, xG, statistics, lineups, injuries, odds, transfers, news | `SPORTMONKS_API_KEY` |
| [The Odds API](https://the-odds-api.com/) | second odds source — best/average/worst price, bookmaker count, movement | `ODDS_API_KEY` |
| [GDELT](https://www.gdeltproject.org/) | global multilingual news search for injury/transfer/manager/dressing-room signal queries | none |

Collectors (`backend/collectors/`) only fetch raw provider JSON. Only
`backend/normalizers/normalize.py` knows a provider's response shape —
everything downstream (`backend/intelligence`, `backend/markets`,
`backend/tickets`) only ever sees the internal normalized schema. This
means adding a second data provider never touches the scoring engine.

**Never commit API keys.** Copy `.env.example` to `.env` locally, and use
GitHub Actions repository secrets (`SPORTMONKS_API_KEY`, `ODDS_API_KEY`)
for the scheduled workflows.

## Automated pipeline (GitHub Actions)

- `.github/workflows/collect.yml` — 05:00 UTC daily full pipeline run
- `.github/workflows/analyse.yml` — intraday reanalysis passes (T-120/T-60/T-30)
- `.github/workflows/settle.yml` — post-match settlement + recalibration

All three commit their JSON output back to the repo, so the frontend (which
reads `data/predictions/*.json` directly, or via the FastAPI backend) always
reflects the latest scheduled run without needing a live database in the
simplest deployment.

## Status / what's stubbed

This is an MVP scaffold, not a finished production system:

- **Live data wiring**: collectors are real, working API clients, but
  `scripts/run_pipeline.py --live` is not yet wired to call them — you'll
  need to map your specific Sportmonks plan's response shape in
  `backend/normalizers/normalize.py` (the sample-data path exercises the
  exact same normalized schema, so this is a mapping exercise, not a
  redesign).
- **HT/FT and both-halves markets** use a simplified half-Poisson
  approximation (documented inline in `backend/markets/survival.py`) rather
  than real half-time xG data — swap in real half splits from Sportmonks
  once available.
- **Goal grid independence assumption**: the Poisson grid treats home/away
  scoring as independent, which slightly overprices low-scoring draws. A
  Dixon-Coles low-score correction (`tau`) is a natural v2 improvement.
- **LLM summarisation layer** (news → structured injury/transfer signal
  extraction) is referenced in the design but not yet implemented as code —
  intentionally kept separate from the probability engine per the "DATA →
  MATHEMATICS → MODEL → LLM EXPLANATION" principle.
- **Persistence**: `backend/db/models.py` defines the SQLAlchemy schema;
  the pipeline currently writes flat JSON/`data/historical` files rather
  than writing through the ORM on every run — wire `scripts/run_pipeline.py`
  to also insert `Prediction` rows once you want SQL-queryable history.

## Stack

Frontend: Next.js 14 + TypeScript · Backend: Python + FastAPI · DB:
PostgreSQL (SQLite locally) via SQLAlchemy · Analytics: pandas/NumPy-ready ·
Automation: GitHub Actions · Suggested deployment: Vercel (frontend) +
Render/Railway (backend).
