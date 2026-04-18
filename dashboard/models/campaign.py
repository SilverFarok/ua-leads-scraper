"""Campaign-related admin models."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dashboard.db.base import AdminBase


def admin_now() -> datetime:
    """Return current UTC timestamp."""
    return datetime.now(timezone.utc)


class CampaignRecord(AdminBase):
    """Campaign metadata for UI-managed scraping runs."""

    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    niche: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    target_mobile_leads: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    default_run_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="full-run")
    setting_profile_id: Mapped[int] = mapped_column(ForeignKey("setting_profiles.id"), nullable=False)
    database_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    output_dir: Mapped[str] = mapped_column(String(1024), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=admin_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=admin_now,
        onupdate=admin_now,
        nullable=False,
    )

    cities: Mapped[list["CampaignCityRecord"]] = relationship(
        back_populates="campaign",
        cascade="all, delete-orphan",
        order_by="CampaignCityRecord.position.asc()",
    )
    runs: Mapped[list["RunJobRecord"]] = relationship(back_populates="campaign")
    setting_profile: Mapped["SettingProfileRecord"] = relationship(back_populates="campaigns")


class CampaignCityRecord(AdminBase):
    """Ordered city list belonging to a campaign."""

    __tablename__ = "campaign_cities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"), nullable=False, index=True)
    city: Mapped[str] = mapped_column(String(255), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    campaign: Mapped["CampaignRecord"] = relationship(back_populates="cities")


from dashboard.models.run_job import RunJobRecord  # noqa: E402  pylint: disable=wrong-import-position
from dashboard.models.setting_profile import SettingProfileRecord  # noqa: E402  pylint: disable=wrong-import-position
