"""SQLite database access layer."""

from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from config import Settings
from models import Base, BusinessLead, BusinessRecord, CandidateRecord, CompanyCandidate, QueryInput, StoredCandidate
from utils.text_utils import canonicalize_url, normalize_name_city_key


class Database:
    """Database helper for persistence and readback."""

    def __init__(self, settings: Settings) -> None:
        self._engine = create_engine(f"sqlite:///{settings.database_path}", future=True)
        self._session_factory = sessionmaker(bind=self._engine, expire_on_commit=False, future=True)

    def init_db(self) -> None:
        """Create SQLite schema."""
        Base.metadata.create_all(self._engine)

    def dispose(self) -> None:
        """Dispose pooled DB connections so SQLite files can be deleted safely."""
        self._engine.dispose()

    @contextmanager
    def session_scope(self) -> Iterator[Session]:
        """Provide a transactional session scope."""
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def save_candidates(self, query: QueryInput, candidates: list[CompanyCandidate]) -> tuple[int, int]:
        """Insert new candidates and merge updates into existing ones.

        Returns `(inserted_count, updated_count)`.
        """
        inserted = 0
        updated = 0

        with self.session_scope() as session:
            for candidate in candidates:
                dedup_key = self.build_candidate_key(candidate.company_name, candidate.city, candidate.website)
                record = session.execute(
                    select(CandidateRecord).where(
                        CandidateRecord.query_niche == query.niche,
                        CandidateRecord.dedup_key == dedup_key,
                    )
                ).scalar_one_or_none()

                if record is None:
                    session.add(
                        CandidateRecord(
                            query_niche=query.niche,
                            query_city=query.city,
                            company_name=candidate.company_name or "Unknown company",
                            city=candidate.city or query.city,
                            website=candidate.website,
                            google_maps_url=candidate.google_maps_url,
                            source=candidate.source,
                            phone_candidates_json=json.dumps(
                                list(dict.fromkeys(candidate.phone_candidates)),
                                ensure_ascii=False,
                            ),
                            dedup_key=dedup_key,
                            enrichment_status="pending",
                        )
                    )
                    inserted += 1
                    continue

                changed = False
                if candidate.website and not record.website:
                    record.website = candidate.website
                    changed = True
                if candidate.google_maps_url and not record.google_maps_url:
                    record.google_maps_url = candidate.google_maps_url
                    changed = True
                if candidate.company_name and record.company_name == "Unknown company":
                    record.company_name = candidate.company_name
                    changed = True

                merged_sources = self._merge_csv_tokens(record.source, candidate.source)
                if merged_sources != record.source:
                    record.source = merged_sources
                    changed = True

                merged_phones = self._merge_phone_candidates(
                    json.loads(record.phone_candidates_json or "[]"),
                    candidate.phone_candidates,
                )
                merged_phones_json = json.dumps(merged_phones, ensure_ascii=False)
                if merged_phones_json != record.phone_candidates_json:
                    record.phone_candidates_json = merged_phones_json
                    changed = True

                if changed and record.enrichment_status == "failed":
                    record.enrichment_status = "pending"
                    record.last_error = None
                if changed:
                    updated += 1

        return inserted, updated

    def fetch_candidates_for_enrichment(self) -> list[StoredCandidate]:
        """Return candidates waiting for enrichment."""
        with self.session_scope() as session:
            records = session.execute(
                select(CandidateRecord)
                .where(CandidateRecord.enrichment_status == "pending")
                .order_by(CandidateRecord.created_at.asc(), CandidateRecord.id.asc())
            ).scalars().all()
        return [record.to_dataclass() for record in records]

    def mark_candidate_processed(
        self,
        candidate_id: int,
        *,
        status: str,
        website: str | None,
        google_maps_url: str | None,
        source: str,
        phone_candidates: list[str],
        last_error: str | None = None,
    ) -> None:
        """Update candidate after enrichment attempt."""
        with self.session_scope() as session:
            record = session.get(CandidateRecord, candidate_id)
            if record is None:
                return
            record.enrichment_status = status
            record.website = website
            record.google_maps_url = google_maps_url
            record.source = source
            record.phone_candidates_json = json.dumps(list(dict.fromkeys(phone_candidates)), ensure_ascii=False)
            record.last_error = last_error

    def save_leads(self, leads: list[BusinessLead]) -> None:
        """Persist new leads to SQLite."""
        if not leads:
            return

        with self.session_scope() as session:
            session.add_all([BusinessRecord.from_lead(lead) for lead in leads])

    def load_dedup_state(self) -> tuple[set[str], set[str]]:
        """Load current deduplication keys from the lead table."""
        phone_keys: set[str] = set()
        business_keys: set[str] = set()

        with self.session_scope() as session:
            records = session.execute(select(BusinessRecord)).scalars().all()

        for record in records:
            if record.phone_normalized:
                phone_keys.add(record.phone_normalized)

            website_key = canonicalize_url(record.website)
            if website_key:
                business_keys.add(website_key)
            else:
                business_keys.add(normalize_name_city_key(record.company_name, record.city))

        return phone_keys, business_keys

    def count_mobile_leads(self) -> int:
        """Return the number of stored mobile leads."""
        with self.session_scope() as session:
            count = session.execute(
                select(func.count(BusinessRecord.id)).where(BusinessRecord.phone_type == "mobile")
            ).scalar_one()
        return int(count)

    def fetch_all_leads(self) -> list[BusinessLead]:
        """Return all stored leads for export."""
        with self.session_scope() as session:
            records = session.execute(
                select(BusinessRecord).order_by(BusinessRecord.created_at.asc(), BusinessRecord.id.asc())
            ).scalars().all()

        return [
            BusinessLead(
                query_niche=record.query_niche,
                query_city=record.query_city,
                company_name=record.company_name,
                city=record.city,
                website=record.website,
                google_maps_url=record.google_maps_url,
                phone_raw=record.phone_raw,
                phone_normalized=record.phone_normalized,
                phone_type=record.phone_type,
                source=record.source,
                created_at=record.created_at,
            )
            for record in records
        ]

    def count_all_candidates(self) -> int:
        """Return the total number of candidate rows."""
        with self.session_scope() as session:
            count = session.execute(select(func.count(CandidateRecord.id))).scalar_one()
        return int(count)

    def count_candidates_by_status(self, status: str) -> int:
        """Return the number of candidates with a given enrichment status."""
        with self.session_scope() as session:
            count = session.execute(
                select(func.count(CandidateRecord.id)).where(CandidateRecord.enrichment_status == status)
            ).scalar_one()
        return int(count)

    def count_all_leads(self) -> int:
        """Return total lead count."""
        with self.session_scope() as session:
            count = session.execute(select(func.count(BusinessRecord.id))).scalar_one()
        return int(count)

    @staticmethod
    def build_candidate_key(company_name: str, city: str, website: str | None) -> str:
        """Build a stable candidate deduplication key."""
        website_key = canonicalize_url(website)
        if website_key:
            return website_key
        return normalize_name_city_key(company_name, city)

    @staticmethod
    def _merge_phone_candidates(existing: list[str], incoming: list[str]) -> list[str]:
        """Merge raw phone candidates preserving order and uniqueness."""
        return list(dict.fromkeys([*existing, *incoming]))

    @staticmethod
    def _merge_csv_tokens(existing: str, incoming: str) -> str:
        """Merge comma-separated source tokens."""
        tokens = []
        for value in [existing, incoming]:
            if not value:
                continue
            tokens.extend(item.strip() for item in value.split(",") if item.strip())
        return ",".join(dict.fromkeys(tokens))
