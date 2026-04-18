"""Enrichment stage for converting candidates into final leads."""

from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
import logging
from dataclasses import dataclass, replace

from config import Settings
from database import Database
from models import BusinessLead, StoredCandidate
from scrapers.search_scraper import SearchScraper
from scrapers.site_scraper import SiteScraper
from utils.http_utils import build_retry_session
from utils.phone_utils import classify_ukrainian_phone, normalize_ukrainian_phone
from utils.text_utils import canonicalize_url, normalize_name_city_key


@dataclass(slots=True)
class EnrichmentStats:
    """Counters for the enrichment stage."""

    candidates_processed: int = 0
    phones_found: int = 0
    mobile_found: int = 0
    leads_saved: int = 0
    duplicates_filtered: int = 0
    errors: int = 0
    stopped_on_target: bool = False


class EnrichmentService:
    """Enrich stored candidates, create leads, and persist them."""

    def __init__(self, settings: Settings, database: Database, logger: logging.Logger) -> None:
        self._settings = settings
        self._database = database
        self._logger = logger

    def run(self) -> EnrichmentStats:
        """Run enrichment for all pending candidates."""
        stats = EnrichmentStats()
        phone_keys, business_keys = self._database.load_dedup_state()
        current_mobile_total = self._database.count_mobile_leads()

        if self._target_reached(current_mobile_total):
            self._logger.info(
                "Target mobile lead count is already reached: %s/%s.",
                current_mobile_total,
                self._settings.target_mobile_leads,
            )
            stats.stopped_on_target = True
            return stats

        pending_candidates = self._database.fetch_candidates_for_enrichment()
        if not pending_candidates:
            self._logger.info("No pending candidates for enrichment.")
            return stats

        with ThreadPoolExecutor(max_workers=self._settings.enrichment_workers) as executor:
            candidate_iter = iter(pending_candidates)
            in_flight: dict[Future[StoredCandidate], StoredCandidate] = {}

            while len(in_flight) < self._settings.enrichment_workers:
                candidate = next(candidate_iter, None)
                if candidate is None:
                    break
                future = executor.submit(self._prepare_candidate, candidate)
                in_flight[future] = candidate

            while in_flight:
                done, _ = wait(in_flight.keys(), return_when=FIRST_COMPLETED)
                for future in done:
                    original_candidate = in_flight.pop(future)
                    stats.candidates_processed += 1

                    try:
                        prepared_candidate = future.result()
                        leads, new_mobile_count = self._emit_leads(
                            candidate=prepared_candidate,
                            phone_keys=phone_keys,
                            business_keys=business_keys,
                            stats=stats,
                        )
                        self._database.save_leads(leads)
                        self._database.mark_candidate_processed(
                            candidate_id=prepared_candidate.id,
                            status="done",
                            website=prepared_candidate.website,
                            google_maps_url=prepared_candidate.google_maps_url,
                            source=prepared_candidate.source,
                            phone_candidates=prepared_candidate.phone_candidates,
                        )
                        stats.leads_saved += len(leads)
                        current_mobile_total += new_mobile_count
                    except Exception as exc:
                        stats.errors += 1
                        self._database.mark_candidate_processed(
                            candidate_id=original_candidate.id,
                            status="failed",
                            website=original_candidate.website,
                            google_maps_url=original_candidate.google_maps_url,
                            source=original_candidate.source,
                            phone_candidates=original_candidate.phone_candidates,
                            last_error=str(exc),
                        )
                        self._logger.exception(
                            "Enrichment failed for candidate_id=%s company='%s'.",
                            original_candidate.id,
                            original_candidate.company_name,
                        )

                    if self._target_reached(current_mobile_total):
                        stats.stopped_on_target = True
                        self._logger.info(
                            "Stopping enrichment after reaching target mobile leads: %s/%s.",
                            current_mobile_total,
                            self._settings.target_mobile_leads,
                        )
                        for queued_future in in_flight:
                            queued_future.cancel()
                        in_flight.clear()
                        break

                    next_candidate = next(candidate_iter, None)
                    if next_candidate is not None:
                        future = executor.submit(self._prepare_candidate, next_candidate)
                        in_flight[future] = next_candidate

        return stats

    def _prepare_candidate(self, candidate: StoredCandidate) -> StoredCandidate:
        """Run network-heavy enrichment for one candidate in a worker thread."""
        working_candidate = replace(candidate)
        session = build_retry_session(self._settings)
        search_scraper = SearchScraper(session, self._settings, self._logger)
        site_scraper = SiteScraper(session, self._settings, self._logger)

        try:
            if not working_candidate.website and working_candidate.company_name:
                working_candidate.website = search_scraper.find_official_website(
                    working_candidate.company_name,
                    working_candidate.city,
                )

            source_tokens = self._split_sources(working_candidate.source)
            if working_candidate.website:
                site_result = site_scraper.scrape(working_candidate.website)
                working_candidate.phone_candidates = list(
                    dict.fromkeys([*working_candidate.phone_candidates, *site_result.phone_candidates])
                )
                if site_result.title and working_candidate.company_name == "Unknown company":
                    working_candidate.company_name = site_result.title
                source_tokens.add("site")

            working_candidate.source = ",".join(sorted(source_tokens)) if source_tokens else "unknown"
            return working_candidate
        finally:
            session.close()

    def _emit_leads(
        self,
        candidate: StoredCandidate,
        phone_keys: set[str],
        business_keys: set[str],
        stats: EnrichmentStats,
    ) -> tuple[list[BusinessLead], int]:
        """Convert an enriched candidate into deduplicated lead rows."""
        leads: list[BusinessLead] = []
        mobile_count = 0
        business_key = self._business_key(candidate.company_name, candidate.city, candidate.website)

        phone_rows: dict[str, tuple[str, str]] = {}
        fallback_unknown_raw: str | None = None

        for raw_phone in sorted(candidate.phone_candidates):
            normalized = normalize_ukrainian_phone(raw_phone)
            if not normalized:
                fallback_unknown_raw = fallback_unknown_raw or raw_phone
                continue

            phone_type = classify_ukrainian_phone(normalized, self._settings.ua_mobile_prefixes)
            phone_rows.setdefault(normalized, (raw_phone, phone_type))

        if not phone_rows:
            if business_key in business_keys:
                stats.duplicates_filtered += 1
                return [], mobile_count

            business_keys.add(business_key)
            return (
                [
                    BusinessLead(
                        query_niche=candidate.query_niche,
                        query_city=candidate.query_city,
                        company_name=candidate.company_name or "Unknown company",
                        city=candidate.city,
                        website=candidate.website,
                        google_maps_url=candidate.google_maps_url,
                        phone_raw=fallback_unknown_raw,
                        phone_normalized=None,
                        phone_type="unknown",
                        source=candidate.source,
                    )
                ],
                mobile_count,
            )

        for normalized_phone, (raw_phone, phone_type) in phone_rows.items():
            stats.phones_found += 1
            if phone_type == "mobile":
                stats.mobile_found += 1

            if normalized_phone in phone_keys:
                stats.duplicates_filtered += 1
                continue

            phone_keys.add(normalized_phone)
            business_keys.add(business_key)
            if phone_type == "mobile":
                mobile_count += 1

            leads.append(
                BusinessLead(
                    query_niche=candidate.query_niche,
                    query_city=candidate.query_city,
                    company_name=candidate.company_name or "Unknown company",
                    city=candidate.city,
                    website=candidate.website,
                    google_maps_url=candidate.google_maps_url,
                    phone_raw=raw_phone,
                    phone_normalized=normalized_phone,
                    phone_type=phone_type,
                    source=candidate.source,
                )
            )

        return leads, mobile_count

    def _target_reached(self, current_mobile_total: int) -> bool:
        """Return True when the configured mobile lead target has been reached."""
        target = self._settings.target_mobile_leads
        return target > 0 and current_mobile_total >= target

    @staticmethod
    def _business_key(company_name: str, city: str, website: str | None) -> str:
        """Build a business deduplication key for final leads."""
        website_key = canonicalize_url(website)
        if website_key:
            return website_key
        return normalize_name_city_key(company_name, city)

    @staticmethod
    def _split_sources(value: str) -> set[str]:
        """Split comma-separated sources into a set."""
        return {item.strip() for item in value.split(",") if item.strip()}
