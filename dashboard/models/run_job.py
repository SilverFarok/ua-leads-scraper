"""Run job admin model."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, Text, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dashboard.db.base import AdminBase


def admin_now() -> datetime:
    """Return current UTC timestamp."""
    return datetime.now(timezone.utc)


class RunJobRecord(AdminBase):
    """Queued or finished execution of a campaign mode."""

    __tablename__ = "run_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"), nullable=False, index=True)
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    candidates_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    leads_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mobile_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicates_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    logs_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=admin_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=admin_now,
        onupdate=admin_now,
        nullable=False,
    )

    campaign: Mapped["CampaignRecord"] = relationship(back_populates="runs")


from dashboard.models.campaign import CampaignRecord  # noqa: E402  pylint: disable=wrong-import-position
