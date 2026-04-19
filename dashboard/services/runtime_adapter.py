"""Adapters that map dashboard campaigns/runs to the existing scraping core."""

from __future__ import annotations

import csv
import logging
import re
from dataclasses import replace
from pathlib import Path

from config import Settings
from database import Database
from exporters.export_service import LeadExportService
from services.discovery_service import DiscoveryService, DiscoveryStats
from services.enrichment_service import EnrichmentService, EnrichmentStats

from dashboard.models import CampaignRecord, SettingProfileRecord


class PipelineAdapter:
    """Bridge between dashboard jobs and the existing scraping services."""

    def __init__(self, base_settings: Settings, logger: logging.Logger) -> None:
        self._base_settings = base_settings
        self._logger = logger

    def run_mode(
        self,
        *,
        campaign: CampaignRecord,
        cities: list[str],
        profile: SettingProfileRecord,
        blocked_domains: tuple[str, ...],
        mode: str,
        run_id: int,
    ) -> dict[str, int]:
        """Execute one run mode against the existing pipeline services."""
        runtime_settings = self._build_runtime_settings(
            campaign=campaign,
            cities=cities,
            profile=profile,
            blocked_domains=blocked_domains,
            run_id=run_id,
        )
        database = Database(runtime_settings)
        database.init_db()
        exporter = LeadExportService(runtime_settings, self._logger)
        try:
            if mode == "discover-only":
                discovery_stats = DiscoveryService(runtime_settings, database, self._logger).run()
                return self._collect_counts(database, discovery_stats=discovery_stats, enrichment_stats=None)

            if mode == "enrich-only":
                enrichment_stats = EnrichmentService(runtime_settings, database, self._logger).run()
                exporter.export(database.fetch_all_leads())
                return self._collect_counts(database, discovery_stats=None, enrichment_stats=enrichment_stats)

            if mode == "export-only":
                exporter.export(database.fetch_all_leads())
                return self._collect_counts(database, discovery_stats=None, enrichment_stats=None)

            discovery_stats = DiscoveryService(runtime_settings, database, self._logger).run()
            enrichment_stats = EnrichmentService(runtime_settings, database, self._logger).run()
            exporter.export(database.fetch_all_leads())
            return self._collect_counts(database, discovery_stats=discovery_stats, enrichment_stats=enrichment_stats)
        finally:
            database.dispose()

    def _build_runtime_settings(
        self,
        *,
        campaign: CampaignRecord,
        cities: list[str],
        profile: SettingProfileRecord,
        blocked_domains: tuple[str, ...],
        run_id: int,
    ) -> Settings:
        """Build an isolated runtime settings object for one campaign run."""
        input_csv = self._write_input_csv(run_id=run_id, niche=campaign.niche, cities=cities)
        output_dir = Path(campaign.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        Path(campaign.database_path).parent.mkdir(parents=True, exist_ok=True)

        return replace(
            self._base_settings,
            input_csv=input_csv,
            database_path=Path(campaign.database_path),
            output_dir=output_dir,
            request_timeout_sec=profile.site_timeout_sec,
            request_delay_sec=profile.request_delay_ms / 1000.0,
            max_search_results_per_query=profile.max_search_results_per_query,
            max_site_pages_per_company=profile.max_site_pages_per_company,
            enrichment_workers=profile.enrichment_workers,
            target_mobile_leads=campaign.target_mobile_leads,
            blocked_domains=blocked_domains,
            google_sheets_worksheet_prefix=self._worksheet_prefix(campaign.name),
        )

    def _write_input_csv(self, *, run_id: int, niche: str, cities: list[str]) -> Path:
        """Create a temporary CSV for the existing discovery service."""
        safe_slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", niche).strip("_") or "campaign"
        jobs_dir = self._base_settings.data_dir / "jobs"
        jobs_dir.mkdir(parents=True, exist_ok=True)
        csv_path = jobs_dir / f"run_{run_id}_{safe_slug}.csv"
        with csv_path.open("w", encoding="utf-8", newline="") as file_handle:
            writer = csv.writer(file_handle)
            writer.writerow(["niche", "city"])
            for city in cities:
                writer.writerow([niche, city])
        return csv_path

    @staticmethod
    def _worksheet_prefix(campaign_name: str) -> str:
        """Build a stable worksheet prefix per campaign."""
        slug = re.sub(r"[^a-zA-Z0-9_\u0400-\u04FF-]+", "_", campaign_name).strip("_")
        return slug[:80] or "campaign"

    def _collect_counts(
        self,
        database: Database,
        *,
        discovery_stats: DiscoveryStats | None,
        enrichment_stats: EnrichmentStats | None,
    ) -> dict[str, int]:
        """Map core stats and database counts to the admin run counters."""
        return {
            "candidates_count": database.count_all_candidates(),
            "leads_count": database.count_all_leads(),
            "mobile_count": database.count_mobile_leads(),
            "duplicates_count": (
                (discovery_stats.candidates_updated if discovery_stats else 0)
                + (enrichment_stats.duplicates_filtered if enrichment_stats else 0)
            ),
            "failed_count": database.count_candidates_by_status("failed"),
        }
