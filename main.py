"""Application entry point."""

from __future__ import annotations

import argparse
import logging
import sys

from config import get_settings
from database import Database
from exporters.excel_exporter import ExcelExporter
from services.discovery_service import DiscoveryService
from services.enrichment_service import EnrichmentService
from utils.logging_utils import configure_logging


def build_parser() -> argparse.ArgumentParser:
    """Create CLI argument parser."""
    parser = argparse.ArgumentParser(description="UA Business Leads MVP")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--discover-only",
        action="store_true",
        help="Run only the discovery phase and save company candidates to SQLite.",
    )
    group.add_argument(
        "--enrich-only",
        action="store_true",
        help="Run only the enrichment phase using existing company candidates from SQLite.",
    )
    group.add_argument(
        "--export-only",
        action="store_true",
        help="Export current SQLite data to XLSX without running new scraping.",
    )
    return parser


def export_only(database: Database, exporter: ExcelExporter, logger: logging.Logger) -> int:
    """Export current database contents without scraping."""
    leads = database.fetch_all_leads()
    full_path, mobile_path = exporter.export(leads)
    logger.info("Export-only mode complete.")
    logger.info("Records exported: %s", len(leads))
    logger.info("full_results.xlsx: %s", full_path)
    logger.info("mobile_only.xlsx: %s", mobile_path)
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run the selected application mode."""
    args = build_parser().parse_args(argv)
    settings = get_settings()
    configure_logging(settings)
    logger = logging.getLogger(__name__)

    database = Database(settings)
    database.init_db()
    exporter = ExcelExporter(settings)

    if args.export_only:
        return export_only(database=database, exporter=exporter, logger=logger)

    discovery_service = DiscoveryService(settings=settings, database=database, logger=logger)
    enrichment_service = EnrichmentService(settings=settings, database=database, logger=logger)

    try:
        if args.discover_only:
            discovery_stats = discovery_service.run()
            logger.info("Discovery complete.")
            logger.info("Queries processed: %s", discovery_stats.queries_processed)
            logger.info("Companies found: %s", discovery_stats.companies_found)
            logger.info("Unique candidates: %s", discovery_stats.unique_candidates)
            logger.info("Candidates inserted: %s", discovery_stats.candidates_inserted)
            logger.info("Candidates updated: %s", discovery_stats.candidates_updated)
            logger.info("Errors: %s", discovery_stats.errors)
            return 0

        if args.enrich_only:
            enrichment_stats = enrichment_service.run()
            full_path, mobile_path = exporter.export(database.fetch_all_leads())
            logger.info("Enrichment complete.")
            logger.info("Candidates processed: %s", enrichment_stats.candidates_processed)
            logger.info("Phones found: %s", enrichment_stats.phones_found)
            logger.info("Mobile phones found: %s", enrichment_stats.mobile_found)
            logger.info("Leads saved: %s", enrichment_stats.leads_saved)
            logger.info("Duplicates filtered: %s", enrichment_stats.duplicates_filtered)
            logger.info("Errors: %s", enrichment_stats.errors)
            logger.info("full_results.xlsx: %s", full_path)
            logger.info("mobile_only.xlsx: %s", mobile_path)
            return 0

        discovery_stats = discovery_service.run()
        enrichment_stats = enrichment_service.run()
        full_path, mobile_path = exporter.export(database.fetch_all_leads())

        logger.info("Run complete.")
        logger.info("Discovery queries processed: %s", discovery_stats.queries_processed)
        logger.info("Discovery companies found: %s", discovery_stats.companies_found)
        logger.info("Discovery unique candidates: %s", discovery_stats.unique_candidates)
        logger.info("Discovery inserted: %s", discovery_stats.candidates_inserted)
        logger.info("Discovery updated: %s", discovery_stats.candidates_updated)
        logger.info("Enrichment candidates processed: %s", enrichment_stats.candidates_processed)
        logger.info("Phones found: %s", enrichment_stats.phones_found)
        logger.info("Mobile phones found: %s", enrichment_stats.mobile_found)
        logger.info("Leads saved: %s", enrichment_stats.leads_saved)
        logger.info("Duplicates filtered: %s", enrichment_stats.duplicates_filtered)
        logger.info("Errors: %s", discovery_stats.errors + enrichment_stats.errors)
        logger.info("full_results.xlsx: %s", full_path)
        logger.info("mobile_only.xlsx: %s", mobile_path)
        return 0
    except Exception:
        logger.exception("Application failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
