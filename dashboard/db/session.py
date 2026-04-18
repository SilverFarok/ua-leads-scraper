"""Admin database session helpers."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from dashboard.db.base import AdminBase
from dashboard.models import blacklist, campaign, run_job, setting_profile  # noqa: F401


class AdminDatabase:
    """SQLite wrapper for dashboard/admin metadata."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        # Background job threads read and write admin metadata from the same SQLite file.
        self._engine = create_engine(
            f"sqlite:///{self._database_path}",
            future=True,
            connect_args={"check_same_thread": False},
        )
        self._session_factory = sessionmaker(bind=self._engine, expire_on_commit=False, future=True)

    def init_db(self) -> None:
        """Create admin tables."""
        AdminBase.metadata.create_all(self._engine)

    @contextmanager
    def session_scope(self) -> Iterator[Session]:
        """Provide a transaction-scoped session."""
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
