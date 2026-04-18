"""Setting profile admin model."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dashboard.db.base import AdminBase


def admin_now() -> datetime:
    """Return current UTC timestamp."""
    return datetime.now(timezone.utc)


class SettingProfileRecord(AdminBase):
    """Tunable runtime profile for campaign execution."""

    __tablename__ = "setting_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    max_search_results_per_query: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    max_site_pages_per_company: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    enrichment_workers: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    request_delay_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=1500)
    site_timeout_sec: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=admin_now, nullable=False)

    campaigns: Mapped[list["CampaignRecord"]] = relationship(back_populates="setting_profile")


from dashboard.models.campaign import CampaignRecord  # noqa: E402  pylint: disable=wrong-import-position
