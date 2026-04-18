"""Domain blacklist admin model."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from dashboard.db.base import AdminBase


def admin_now() -> datetime:
    """Return current UTC timestamp."""
    return datetime.now(timezone.utc)


class DomainBlacklistRecord(AdminBase):
    """Blocked domain used by runtime adapters."""

    __tablename__ = "domain_blacklist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    domain: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=admin_now, nullable=False)
