"""Database engine/session setup. Defaults to a local SQLite file so the
project runs with zero external dependencies out of the box; point
DATABASE_URL at Postgres in production (e.g. Render/Railway)."""
from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db.models import Base

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./football_intelligence.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def get_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
