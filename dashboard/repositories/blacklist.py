"""Domain blacklist repository."""

from __future__ import annotations

from sqlalchemy import select

from dashboard.db.session import AdminDatabase
from dashboard.models import DomainBlacklistRecord


class DomainBlacklistRepository:
    """CRUD helpers for blocked domains."""

    def __init__(self, admin_db: AdminDatabase) -> None:
        self._admin_db = admin_db

    def list_domains(self) -> list[DomainBlacklistRecord]:
        """Return blacklist ordered by domain."""
        with self._admin_db.session_scope() as session:
            return session.execute(
                select(DomainBlacklistRecord).order_by(DomainBlacklistRecord.domain.asc())
            ).scalars().all()

    def create_domain(self, domain: str, reason: str | None) -> DomainBlacklistRecord:
        """Add a domain to the blacklist."""
        with self._admin_db.session_scope() as session:
            normalized_domain = domain.lower().strip()
            existing = session.execute(
                select(DomainBlacklistRecord).where(DomainBlacklistRecord.domain == normalized_domain)
            ).scalar_one_or_none()
            if existing is not None:
                existing.reason = reason
                session.flush()
                session.refresh(existing)
                return existing

            record = DomainBlacklistRecord(domain=normalized_domain, reason=reason)
            session.add(record)
            session.flush()
            session.refresh(record)
            return record

    def delete_domain(self, blacklist_id: int) -> None:
        """Delete a blacklist row."""
        with self._admin_db.session_scope() as session:
            record = session.get(DomainBlacklistRecord, blacklist_id)
            if record is not None:
                session.delete(record)

    def blocked_domains(self) -> tuple[str, ...]:
        """Return domains as a tuple for runtime settings."""
        return tuple(record.domain for record in self.list_domains())
