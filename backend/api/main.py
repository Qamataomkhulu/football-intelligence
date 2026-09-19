"""
FastAPI app exposing the pipeline's output to the frontend.

By design this API is a thin read layer: scripts/run_pipeline.py does the
actual analysis (deterministic, offline-runnable, scheduled by GitHub
Actions) and writes JSON snapshots to data/predictions/latest.json. This
app just serves that file (and, once the DB has history, calibration
queries) - it never recomputes probabilities on request, so the website
always shows exactly what the audited pipeline run produced.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "predictions"
LATEST_FILE = DATA_DIR / "latest.json"

app = FastAPI(title="Football Intelligence Engine API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to the deployed frontend origin in production
    allow_methods=["GET"],
    allow_headers=["*"],
)


def _load_latest() -> dict:
    if not LATEST_FILE.exists():
        raise HTTPException(
            status_code=404,
            detail="No pipeline output yet. Run scripts/run_pipeline.py to generate data/predictions/latest.json.",
        )
    return json.loads(LATEST_FILE.read_text())


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/dashboard")
def dashboard() -> dict:
    """Summary counts + Ticket A / Ticket B, exactly what the homepage
    dashboard renders."""
    return _load_latest()


@app.get("/api/fixtures/{fixture_id}")
def fixture_detail(fixture_id: str) -> dict:
    """Full intelligence page for one fixture: consensus, reasons, risks,
    all priced markets, and the engine's final choice."""
    data = _load_latest()
    for f in data.get("fixtures", []):
        if f["fixture_id"] == fixture_id:
            return f
    raise HTTPException(status_code=404, detail=f"Fixture {fixture_id} not found in latest run")


@app.get("/api/tickets/{ticket}")
def ticket(ticket: str) -> dict:
    data = _load_latest()
    key = f"ticket_{ticket.lower()}"
    if key not in data.get("tickets", {}):
        raise HTTPException(status_code=404, detail=f"Unknown ticket '{ticket}'")
    return data["tickets"][key]


@app.get("/api/performance")
def performance() -> dict:
    """Calibration + hit-rate history. Reads data/predictions/performance.json,
    written by scripts/settle_results.py after each matchday."""
    perf_file = DATA_DIR / "performance.json"
    if not perf_file.exists():
        raise HTTPException(status_code=404, detail="No performance history yet.")
    return json.loads(perf_file.read_text())
