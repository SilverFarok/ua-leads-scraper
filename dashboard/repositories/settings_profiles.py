"""Setting profile repository."""

from __future__ import annotations

from sqlalchemy import select

from dashboard.db.session import AdminDatabase
from dashboard.models import SettingProfileRecord


class SettingProfileRepository:
    """CRUD for runtime setting profiles."""

    def __init__(self, admin_db: AdminDatabase) -> None:
        self._admin_db = admin_db

    def list_profiles(self) -> list[SettingProfileRecord]:
        """Return all profiles ordered by name."""
        with self._admin_db.session_scope() as session:
            return session.execute(
                select(SettingProfileRecord).order_by(SettingProfileRecord.name.asc())
            ).scalars().all()

    def get_profile(self, profile_id: int) -> SettingProfileRecord | None:
        """Return one profile or None."""
        with self._admin_db.session_scope() as session:
            return session.get(SettingProfileRecord, profile_id)

    def create_profile(
        self,
        *,
        name: str,
        max_search_results_per_query: int,
        max_site_pages_per_company: int,
        enrichment_workers: int,
        request_delay_ms: int,
        site_timeout_sec: int,
    ) -> SettingProfileRecord:
        """Create a setting profile."""
        with self._admin_db.session_scope() as session:
            record = SettingProfileRecord(
                name=name,
                max_search_results_per_query=max_search_results_per_query,
                max_site_pages_per_company=max_site_pages_per_company,
                enrichment_workers=enrichment_workers,
                request_delay_ms=request_delay_ms,
                site_timeout_sec=site_timeout_sec,
            )
            session.add(record)
            session.flush()
            session.refresh(record)
            return record

    def ensure_default_profile(self) -> None:
        """Create a default profile if the table is empty."""
        with self._admin_db.session_scope() as session:
            existing = session.execute(select(SettingProfileRecord).limit(1)).scalar_one_or_none()
            if existing is not None:
                return
            session.add(
                SettingProfileRecord(
                    name="Default",
                    max_search_results_per_query=30,
                    max_site_pages_per_company=3,
                    enrichment_workers=5,
                    request_delay_ms=1500,
                    site_timeout_sec=20,
                )
            )
