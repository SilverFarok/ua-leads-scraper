"""Discovery stage for finding company candidates."""

from __future__ import annotations

import csv
import logging
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

from config import Settings
from database import Database
from models import CompanyCandidate, QueryInput
from scrapers.maps_scraper import GoogleMapsScraper
from scrapers.search_scraper import SearchScraper
from utils.http_utils import build_retry_session
from utils.text_utils import canonicalize_url, normalize_name_city_key


@dataclass(slots=True)
class DiscoveryStats:
    """Counters for the discovery stage."""

    queries_processed: int = 0
    companies_found: int = 0
    unique_candidates: int = 0
    candidates_inserted: int = 0
    candidates_updated: int = 0
    errors: int = 0


class DiscoveryService:
    """Collect business candidates and save them for later enrichment."""

    def __init__(self, settings: Settings, database: Database, logger: logging.Logger) -> None:
        self._settings = settings
        self._database = database
        self._logger = logger

    def run(self) -> DiscoveryStats:
        """Run discovery against all queries from the input CSV."""
        stats = DiscoveryStats()
        session = build_retry_session(self._settings)
        search_scraper = SearchScraper(session, self._settings, self._logger)

        try:
            with self._maps_scraper_context() as maps_scraper:
                for query in self._load_queries():
                    stats.queries_processed += 1
                    try:
                        candidates = self._discover_candidates(query, maps_scraper, search_scraper)
                        stats.companies_found += len(candidates)

                        unique_candidates = self._merge_candidates(query, candidates)
                        inserted, updated = self._database.save_candidates(
                            query=query,
                            candidates=list(unique_candidates.values()),
                        )
                        stats.unique_candidates += len(unique_candidates)
                        stats.candidates_inserted += inserted
                        stats.candidates_updated += updated
                    except Exception:
                        stats.errors += 1
                        self._logger.exception(
                            "Discovery failed for niche='%s' city='%s'.",
                            query.niche,
                            query.city,
                        )
        finally:
            session.close()

        return stats

    @contextmanager
    def _maps_scraper_context(self) -> Iterator[GoogleMapsScraper | None]:
        """Yield an active Maps scraper or None if the browser is unavailable."""
        scraper = GoogleMapsScraper(self._settings, self._logger)
        try:
            with scraper as active_scraper:
                yield active_scraper
        except Exception:
            self._logger.warning(
                "Google Maps scraper is unavailable. Falling back to HTML search only. "
                "Run 'python -m playwright install chromium' to enable Maps scraping."
            )
            yield None

    def _load_queries(self) -> list[QueryInput]:
        """Read CSV input file and return query pairs."""
        queries: list[QueryInput] = []
        with self._settings.input_csv.open("r", encoding="utf-8-sig", newline="") as file_handle:
            reader = csv.DictReader(file_handle)
            for row in reader:
                niche = (row.get("niche") or "").strip()
                city = (row.get("city") or "").strip()
                if niche and city:
                    queries.append(QueryInput(niche=niche, city=city))

        if not queries:
            raise ValueError(f"No valid queries found in {self._settings.input_csv}")
        return queries

    def _discover_candidates(
        self,
        query: QueryInput,
        maps_scraper: GoogleMapsScraper | None,
        search_scraper: SearchScraper,
    ) -> list[CompanyCandidate]:
        """Discover companies using Maps first and HTML search as fallback."""
        if maps_scraper is not None:
            try:
                candidates = maps_scraper.search(query.niche, query.city)
                if candidates:
                    return candidates
            except Exception:
                self._logger.warning(
                    "Google Maps discovery failed for '%s / %s'. Falling back to HTML search.",
                    query.niche,
                    query.city,
                    exc_info=True,
                )
        return search_scraper.search_businesses(query.niche, query.city)

    def _merge_candidates(
        self,
        query: QueryInput,
        candidates: list[CompanyCandidate],
    ) -> dict[str, CompanyCandidate]:
        """Merge duplicate candidates within one discovery query."""
        merged: dict[str, CompanyCandidate] = {}
        for candidate in candidates:
            key = self._candidate_key(candidate.company_name, candidate.city or query.city, candidate.website)
            existing = merged.get(key)
            if existing is None:
                merged[key] = CompanyCandidate(
                    company_name=candidate.company_name or "Unknown company",
                    city=candidate.city or query.city,
                    website=candidate.website,
                    google_maps_url=candidate.google_maps_url,
                    source=candidate.source,
                    phone_candidates=list(dict.fromkeys(candidate.phone_candidates)),
                )
                continue

            if candidate.website and not existing.website:
                existing.website = candidate.website
            if candidate.google_maps_url and not existing.google_maps_url:
                existing.google_maps_url = candidate.google_maps_url
            if existing.company_name == "Unknown company" and candidate.company_name:
                existing.company_name = candidate.company_name

            existing.source = self._merge_sources(existing.source, candidate.source)
            existing.phone_candidates = list(
                dict.fromkeys([*existing.phone_candidates, *candidate.phone_candidates])
            )

        return merged

    @staticmethod
    def _candidate_key(company_name: str, city: str, website: str | None) -> str:
        """Build a candidate aggregation key."""
        website_key = canonicalize_url(website)
        if website_key:
            return website_key
        return normalize_name_city_key(company_name, city)

    @staticmethod
    def _merge_sources(existing: str, incoming: str) -> str:
        """Merge comma-separated source labels."""
        tokens = []
        for value in [existing, incoming]:
            if not value:
                continue
            tokens.extend(item.strip() for item in value.split(",") if item.strip())
        return ",".join(dict.fromkeys(tokens))
