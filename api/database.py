"""SQLAlchemy database connection.

The engine is created by the shared toolkit ``astk.db.make_engine`` rather than
a local ``create_engine`` call: it is cached per URL, defaults to
``pool_pre_ping=True``, and is SQLite-in-memory safe (``StaticPool`` +
``check_same_thread=False``) so tests that point ``DATABASE_URL`` at SQLite
behave the same as production Postgres. ``healthcheck``/``wait_for_db`` from the
same module back the ``/health`` endpoint and the startup readiness check.

astk lives in the private ``analytics-service-toolkit`` repo. Production images
install it via a BuildKit secret, but the lightweight CI environment does not
(same situation as ``src/config.py`` and ``src/alert_manager.py``). Without a
fallback here, ``import api.database`` raised ``ModuleNotFoundError`` in CI, the
``client`` fixture in ``tests/conftest.py`` caught it as an ``ImportError`` and
every API test skipped as "fastapi not installed" although fastapi was
installed. The fallback below reproduces the two behaviours of astk's helpers
that the API and its tests rely on, using SQLAlchemy only:

* ``make_engine``: ``pool_pre_ping=True``; for SQLite, ``check_same_thread=False``
  and, for an in-memory URL, ``StaticPool`` so every session sees one database.
* ``healthcheck``: runs ``SELECT 1`` and returns ``True``/``False``, never raises.
"""
from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.pool import StaticPool

try:
    from astk.db import healthcheck, make_engine
except ModuleNotFoundError:  # exercised in the lightweight CI env (no astk)
    _ENGINES: dict[str, Engine] = {}

    def make_engine(url: str) -> Engine:
        """SQLAlchemy-only stand-in for ``astk.db.make_engine`` (cached per URL)."""
        if url not in _ENGINES:
            kwargs: dict = {"pool_pre_ping": True}
            if url.startswith("sqlite"):
                kwargs["connect_args"] = {"check_same_thread": False}
                if url == "sqlite://" or ":memory:" in url:
                    kwargs["poolclass"] = StaticPool
            _ENGINES[url] = create_engine(url, **kwargs)
        return _ENGINES[url]

    def healthcheck(engine: Engine) -> bool:
        """SQLAlchemy-only stand-in for ``astk.db.healthcheck``: ``SELECT 1``, never raises."""
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

from src.config import DATABASE_URL

engine = make_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency: yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
