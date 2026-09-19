"""SQLAlchemy models for persisted predictions and calibration history.

The daily pipeline (scripts/run_pipeline.py) writes JSON snapshots to
data/predictions/ for the website to read (cheap, stateless, git-diffable),
and ALSO writes a row here per selection so backend/calibration can query
historical performance with SQL once volume grows beyond flat files.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Fixture(Base):
    __tablename__ = "fixtures"

    id = Column(Integer, primary_key=True)
    provider_fixture_id = Column(String, unique=True, index=True, nullable=False)
    league = Column(String, nullable=False)
    home_team = Column(String, nullable=False)
    away_team = Column(String, nullable=False)
    kickoff_utc = Column(DateTime, nullable=False)
    home_score = Column(Integer, nullable=True)
    away_score = Column(Integer, nullable=True)
    settled = Column(Boolean, default=False)

    predictions = relationship("Prediction", back_populates="fixture")


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True)
    fixture_id = Column(Integer, ForeignKey("fixtures.id"), nullable=False)
    ticket = Column(String, nullable=False)  # "A", "B", or "C"
    market_code = Column(String, nullable=False)
    label = Column(String, nullable=False)
    model_probability = Column(Float, nullable=False)
    market_implied_probability = Column(Float, nullable=True)
    edge_ratio = Column(Float, nullable=True)
    consensus_gap_pp = Column(Float, nullable=False)
    trap_score = Column(Float, nullable=False)
    reasons_json = Column(Text, nullable=True)  # JSON-encoded list[str]
    risks_json = Column(Text, nullable=True)

    generated_at = Column(DateTime, default=dt.datetime.utcnow)
    settled = Column(Boolean, default=False)
    won = Column(Boolean, nullable=True)
    loss_type = Column(String, nullable=True)

    fixture = relationship("Fixture", back_populates="predictions")
