"""Campaign repository."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import func, select

from dashboard.db.session import AdminDatabase
from dashboard.models import CampaignCityRecord, CampaignRecord, RunJobRecord


class CampaignRepository:
    """CRUD helpers for campaigns and campaign summaries."""

    def __init__(self, admin_db: AdminDatabase) -> None:
        self._admin_db = admin_db

    def list_campaigns(self) -> list[CampaignRecord]:
        """Return campaigns ordered by name."""
        with self._admin_db.session_scope() as session:
            return session.execute(select(CampaignRecord).order_by(CampaignRecord.name.asc())).scalars().all()

    def get_campaign(self, campaign_id: int) -> CampaignRecord | None:
        """Return one campaign or None."""
        with self._admin_db.session_scope() as session:
            return session.get(CampaignRecord, campaign_id)

    def create_campaign(
        self,
        *,
        name: str,
        niche: str,
        cities: list[str],
        target_mobile_leads: int,
        setting_profile_id: int,
        default_run_mode: str,
        database_path: Path,
        output_dir: Path,
        notes: str | None,
    ) -> CampaignRecord:
        """Create a campaign and its city list."""
        with self._admin_db.session_scope() as session:
            record = CampaignRecord(
                name=name,
                niche=niche,
                target_mobile_leads=target_mobile_leads,
                setting_profile_id=setting_profile_id,
                default_run_mode=default_run_mode,
                database_path=str(database_path),
                output_dir=str(output_dir),
                notes=notes,
            )
            session.add(record)
            session.flush()
            session.add_all(
                [
                    CampaignCityRecord(campaign_id=record.id, city=city, position=index)
                    for index, city in enumerate(cities)
                ]
            )
            session.flush()
            session.refresh(record)
            return record

    def list_cities(self, campaign_id: int) -> list[CampaignCityRecord]:
        """Return cities for a campaign."""
        with self._admin_db.session_scope() as session:
            return session.execute(
                select(CampaignCityRecord)
                .where(CampaignCityRecord.campaign_id == campaign_id)
                .order_by(CampaignCityRecord.position.asc())
            ).scalars().all()

    def recent_runs(self, campaign_id: int, limit: int = 10) -> list[RunJobRecord]:
        """Return recent runs for one campaign."""
        with self._admin_db.session_scope() as session:
            return session.execute(
                select(RunJobRecord)
                .where(RunJobRecord.campaign_id == campaign_id)
                .order_by(RunJobRecord.created_at.desc())
                .limit(limit)
            ).scalars().all()

    def campaign_run_summary(self, campaign_id: int) -> dict[str, int]:
        """Aggregate run counters for one campaign."""
        with self._admin_db.session_scope() as session:
            row = session.execute(
                select(
                    func.count(RunJobRecord.id),
                    func.coalesce(func.sum(RunJobRecord.candidates_count), 0),
                    func.coalesce(func.sum(RunJobRecord.leads_count), 0),
                    func.coalesce(func.sum(RunJobRecord.mobile_count), 0),
                    func.coalesce(func.sum(RunJobRecord.duplicates_count), 0),
                    func.coalesce(func.sum(RunJobRecord.failed_count), 0),
                ).where(RunJobRecord.campaign_id == campaign_id)
            ).one()
        return {
            "runs_count": int(row[0]),
            "candidates_count": int(row[1]),
            "leads_count": int(row[2]),
            "mobile_count": int(row[3]),
            "duplicates_count": int(row[4]),
            "failed_count": int(row[5]),
        }
