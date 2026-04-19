"""Background job execution for dashboard-triggered runs."""

from __future__ import annotations

import logging
from pathlib import Path

from config import Settings, get_settings

from dashboard.db.session import AdminDatabase
from dashboard.repositories.blacklist import DomainBlacklistRepository
from dashboard.repositories.campaigns import CampaignRepository
from dashboard.repositories.runs import RunJobRepository
from dashboard.repositories.settings_profiles import SettingProfileRepository
from dashboard.services.runtime_adapter import PipelineAdapter


class RunJobLogHandler(logging.Handler):
    """Logging handler that appends log lines into a run row."""

    def __init__(self, run_repository: RunJobRepository, run_id: int) -> None:
        super().__init__()
        self._run_repository = run_repository
        self._run_id = run_id

    def emit(self, record: logging.LogRecord) -> None:
        """Append one formatted log line."""
        message = self.format(record)
        self._run_repository.append_log(self._run_id, message)


def execute_run_job_subprocess(run_id: int, admin_db_path: str) -> None:
    """Entry point for running one job in a dedicated Python subprocess."""
    settings = get_settings()
    admin_db = AdminDatabase(Path(admin_db_path))
    execute_run_job(run_id, admin_db, settings)


def execute_run_job(run_id: int, admin_db: AdminDatabase, base_settings: Settings) -> None:
    """Load a queued run, execute it, and persist counters/logs."""
    run_repository = RunJobRepository(admin_db)
    campaign_repository = CampaignRepository(admin_db)
    profile_repository = SettingProfileRepository(admin_db)
    blacklist_repository = DomainBlacklistRepository(admin_db)

    run = run_repository.get_run(run_id)
    if run is None:
        return

    campaign = campaign_repository.get_campaign(run.campaign_id)
    if campaign is None:
        run_repository.mark_finished(
            run_id,
            status="failed",
            candidates_count=0,
            leads_count=0,
            mobile_count=0,
            duplicates_count=0,
            failed_count=0,
            error_message="Campaign not found.",
        )
        return

    cities = [row.city for row in campaign_repository.list_cities(campaign.id)]
    profile = profile_repository.get_profile(campaign.setting_profile_id)
    if profile is None:
        run_repository.mark_finished(
            run_id,
            status="failed",
            candidates_count=0,
            leads_count=0,
            mobile_count=0,
            duplicates_count=0,
            failed_count=0,
            error_message="Setting profile not found.",
        )
        return

    logger = logging.getLogger(f"dashboard.run.{run_id}")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    handler = RunJobLogHandler(run_repository, run_id)
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", "%Y-%m-%d %H:%M:%S"))
    logger.addHandler(handler)

    run_repository.mark_running(run_id)
    adapter = PipelineAdapter(base_settings=base_settings, logger=logger)

    try:
        counts = adapter.run_mode(
            campaign=campaign,
            cities=cities,
            profile=profile,
            blocked_domains=blacklist_repository.blocked_domains(),
            mode=run.mode,
            run_id=run_id,
        )
        run_repository.mark_finished(
            run_id,
            status="finished",
            candidates_count=counts["candidates_count"],
            leads_count=counts["leads_count"],
            mobile_count=counts["mobile_count"],
            duplicates_count=counts["duplicates_count"],
            failed_count=counts["failed_count"],
        )
    except Exception as exc:
        logger.exception("Run execution failed.")
        run_repository.mark_finished(
            run_id,
            status="failed",
            candidates_count=0,
            leads_count=0,
            mobile_count=0,
            duplicates_count=0,
            failed_count=0,
            error_message=str(exc),
        )
