"""Pytest fixtures."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from pengelola_keuangan.db.models import Base
from pengelola_keuangan.db.session import reset_engine_for_tests


@pytest.fixture(autouse=True)
def _isolate_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Provide test-safe defaults for the Settings env."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("DEFAULT_TIMEZONE", "Asia/Jakarta")
    monkeypatch.setenv("DEFAULT_CURRENCY", "IDR")
    monkeypatch.setenv("ALLOWED_USER_IDS", "")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    # Force re-load of settings.
    from pengelola_keuangan import config

    config._settings = None  # type: ignore[attr-defined]
    reset_engine_for_tests()
    yield
    config._settings = None  # type: ignore[attr-defined]
    reset_engine_for_tests()


@pytest.fixture
def session() -> Iterator[Session]:
    """Provide a fresh in-memory SQLite session with the schema created."""
    db_path = os.environ["DATABASE_URL"]
    engine = create_engine(db_path, future=True, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    db = factory()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()
