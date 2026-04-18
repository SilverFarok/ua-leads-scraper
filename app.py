"""FastAPI application for the local admin dashboard."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from config import get_settings
from dashboard.db.session import AdminDatabase
from dashboard.repositories.blacklist import DomainBlacklistRepository
from dashboard.repositories.campaigns import CampaignRepository
from dashboard.repositories.runs import RunJobRepository
from dashboard.repositories.settings_profiles import SettingProfileRepository
from dashboard.routes import blacklist, campaigns, runs, settings_profiles
from dashboard.worker.job_manager import JobManager


def create_app() -> FastAPI:
    """Create and configure the FastAPI app."""
    base_settings = get_settings()
    admin_db_path = base_settings.data_dir / "admin.sqlite3"
    admin_db = AdminDatabase(admin_db_path)
    admin_db.init_db()

    profile_repository = SettingProfileRepository(admin_db)
    profile_repository.ensure_default_profile()

    app = FastAPI(title="Lead Scraper Dashboard")
    templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))
    app.mount("/static", StaticFiles(directory=str(Path(__file__).resolve().parent / "static")), name="static")

    app.state.base_settings = base_settings
    app.state.admin_db = admin_db
    app.state.campaign_repository = CampaignRepository(admin_db)
    app.state.run_repository = RunJobRepository(admin_db)
    app.state.profile_repository = profile_repository
    app.state.blacklist_repository = DomainBlacklistRepository(admin_db)
    app.state.job_manager = JobManager(admin_db=admin_db, base_settings=base_settings)

    app.include_router(campaigns.build_router(templates))
    app.include_router(runs.build_router(templates))
    app.include_router(settings_profiles.build_router(templates))
    app.include_router(blacklist.build_router(templates))

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        return RedirectResponse(url="/campaigns", status_code=302)

    return app


app = create_app()
