"""Domain and database models."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    """Return current UTC time."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Base class for ORM models."""


@dataclass(slots=True)
class QueryInput:
    """Input search pair from CSV."""

    niche: str
    city: str


@dataclass(slots=True)
class CompanyCandidate:
    """Candidate business discovered from maps or search results."""

    company_name: str
    city: str
    website: str | None
    google_maps_url: str | None
    source: str
    phone_candidates: list[str] = field(default_factory=list)


@dataclass(slots=True)
class StoredCandidate:
    """Candidate stored in SQLite and ready for enrichment."""

    id: int
    query_niche: str
    query_city: str
    company_name: str
    city: str
    website: str | None
    google_maps_url: str | None
    source: str
    phone_candidates: list[str]
    dedup_key: str
    enrichment_status: str
    last_error: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class SiteScrapeResult:
    """Contact information extracted from a company website."""

    website: str
    title: str | None
    phone_candidates: list[str]
    visited_urls: list[str] = field(default_factory=list)


@dataclass(slots=True)
class BusinessLead:
    """Normalized lead representation used by the pipeline and exporter."""

    query_niche: str
    query_city: str
    company_name: str
    city: str
    website: str | None
    google_maps_url: str | None
    phone_raw: str | None
    phone_normalized: str | None
    phone_type: str
    source: str
    created_at: datetime = field(default_factory=utc_now)


class CandidateRecord(Base):
    """SQLite record for discovered companies before full enrichment."""

    __tablename__ = "company_candidates"
    __table_args__ = (
        UniqueConstraint("query_niche", "dedup_key", name="uq_company_candidates_query_niche_dedup_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    query_niche: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    query_city: Mapped[str] = mapped_column(String(255), nullable=False)
    company_name: Mapped[str] = mapped_column(String(512), nullable=False)
    city: Mapped[str] = mapped_column(String(255), nullable=False)
    website: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    google_maps_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    phone_candidates_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    dedup_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    enrichment_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    def to_dataclass(self) -> StoredCandidate:
        """Convert ORM model to dataclass."""
        return StoredCandidate(
            id=self.id,
            query_niche=self.query_niche,
            query_city=self.query_city,
            company_name=self.company_name,
            city=self.city,
            website=self.website,
            google_maps_url=self.google_maps_url,
            source=self.source,
            phone_candidates=json.loads(self.phone_candidates_json or "[]"),
            dedup_key=self.dedup_key,
            enrichment_status=self.enrichment_status,
            last_error=self.last_error,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


class BusinessRecord(Base):
    """SQLite record for discovered business contacts."""

    __tablename__ = "business_leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    query_niche: Mapped[str] = mapped_column(String(255), nullable=False)
    query_city: Mapped[str] = mapped_column(String(255), nullable=False)
    company_name: Mapped[str] = mapped_column(String(512), nullable=False)
    city: Mapped[str] = mapped_column(String(255), nullable=False)
    website: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    google_maps_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    phone_raw: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone_normalized: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    phone_type: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    @classmethod
    def from_lead(cls, lead: BusinessLead) -> "BusinessRecord":
        """Build ORM object from dataclass."""
        return cls(
            query_niche=lead.query_niche,
            query_city=lead.query_city,
            company_name=lead.company_name,
            city=lead.city,
            website=lead.website,
            google_maps_url=lead.google_maps_url,
            phone_raw=lead.phone_raw,
            phone_normalized=lead.phone_normalized,
            phone_type=lead.phone_type,
            source=lead.source,
            created_at=lead.created_at,
        )
