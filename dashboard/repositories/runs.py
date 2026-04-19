"""Run job repository."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from dashboard.db.session import AdminDatabase
from dashboard.models import RunJobRecord


def utc_now() -> datetime:
    """Return current UTC time."""
    return datetime.now(timezone.utc)


class RunJobRepository:
    """Persistence helpers for background jobs."""

    def __init__(self, admin_db: AdminDatabase) -> None:
        self._admin_db = admin_db

    def create_run(self, campaign_id: int, mode: str) -> RunJobRecord:
        """Create a queued run entry."""
        with self._admin_db.session_scope() as session:
            record = RunJobRecord(campaign_id=campaign_id, mode=mode, status="queued")
            session.add(record)
            session.flush()
            session.refresh(record)
            return record

    def list_runs(self, limit: int = 100) -> list[RunJobRecord]:
        """Return latest runs."""
        with self._admin_db.session_scope() as session:
            return session.execute(
                select(RunJobRecord).order_by(RunJobRecord.created_at.desc()).limit(limit)
            ).scalars().all()

    def get_run(self, run_id: int) -> RunJobRecord | None:
        """Return one run or None."""
        with self._admin_db.session_scope() as session:
            return session.get(RunJobRecord, run_id)

    def mark_running(self, run_id: int) -> None:
        """Set a run to running state."""
        with self._admin_db.session_scope() as session:
            record = session.get(RunJobRecord, run_id)
            if record is None:
                return
            record.status = "running"
            record.started_at = utc_now()
            record.error_message = None

    def mark_finished(
        self,
        run_id: int,
        *,
        status: str,
        candidates_count: int,
        leads_count: int,
        mobile_count: int,
        duplicates_count: int,
        failed_count: int,
        error_message: str | None = None,
    ) -> None:
        """Finalize a run with counters and optional error."""
        with self._admin_db.session_scope() as session:
            record = session.get(RunJobRecord, run_id)
            if record is None:
                return
            record.status = status
            record.finished_at = utc_now()
            record.candidates_count = candidates_count
            record.leads_count = leads_count
            record.mobile_count = mobile_count
            record.duplicates_count = duplicates_count
            record.failed_count = failed_count
            record.error_message = error_message

    def append_log(self, run_id: int, message: str) -> None:
        """Append one log line to the run."""
        with self._admin_db.session_scope() as session:
            record = session.get(RunJobRecord, run_id)
            if record is None:
                return
            record.logs_text = f"{record.logs_text}{message}\n"

    def delete_run(self, run_id: int) -> RunJobRecord | None:
        """Delete one run and return its last known record."""
        with self._admin_db.session_scope() as session:
            record = session.get(RunJobRecord, run_id)
            if record is None:
                return None
            session.delete(record)
            return record

    def campaign_has_active_runs(self, campaign_id: int) -> bool:
        """Return True when a campaign still has queued or running jobs."""
        with self._admin_db.session_scope() as session:
            return (
                session.execute(
                    select(RunJobRecord.id).where(
                        RunJobRecord.campaign_id == campaign_id,
                        RunJobRecord.status.in_(("queued", "running")),
                    )
                ).first()
                is not None
            )
