"""Campaign routes."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from dashboard.repositories.campaigns import CampaignRepository
from dashboard.repositories.runs import RunJobRepository
from dashboard.repositories.settings_profiles import SettingProfileRepository
from dashboard.routes.deps import campaign_repository, profile_repository, run_repository
from dashboard.schemas.forms import CampaignCreateForm

ALLOWED_RUN_MODES = {"discover-only", "enrich-only", "full-run", "export-only"}


def build_router(templates: Jinja2Templates) -> APIRouter:
    """Create campaign router."""
    router = APIRouter()

    @router.get("/campaigns", response_class=HTMLResponse)
    def list_campaigns(
        request: Request,
        campaigns_repo: CampaignRepository = Depends(campaign_repository),
    ) -> HTMLResponse:
        campaigns = campaigns_repo.list_campaigns()
        return templates.TemplateResponse(
            "campaigns/list.html",
            {"request": request, "campaigns": campaigns},
        )

    @router.get("/campaigns/new", response_class=HTMLResponse)
    def new_campaign_form(
        request: Request,
        profiles_repo: SettingProfileRepository = Depends(profile_repository),
    ) -> HTMLResponse:
        return templates.TemplateResponse(
            "campaigns/new.html",
            {"request": request, "profiles": profiles_repo.list_profiles()},
        )

    @router.post("/campaigns/new")
    def create_campaign(
        request: Request,
        name: str = Form(...),
        niche: str = Form(...),
        cities_text: str = Form(...),
        target_mobile_leads: int = Form(0),
        setting_profile_id: int = Form(...),
        default_run_mode: str = Form(...),
        notes: str = Form(""),
        campaigns_repo: CampaignRepository = Depends(campaign_repository),
    ) -> RedirectResponse:
        form = CampaignCreateForm(
            name=name,
            niche=niche,
            cities_text=cities_text,
            target_mobile_leads=target_mobile_leads,
            setting_profile_id=setting_profile_id,
            default_run_mode=default_run_mode,
            notes=notes or None,
        )
        cities = [line.strip() for line in form.cities_text.splitlines() if line.strip()]
        safe_slug = "".join(char.lower() if char.isalnum() else "_" for char in form.name).strip("_") or "campaign"
        campaign_db_path = Path(request.app.state.base_settings.data_dir) / "campaigns" / f"{safe_slug}.sqlite3"
        campaign_output_dir = Path(request.app.state.base_settings.output_dir) / safe_slug
        campaign = campaigns_repo.create_campaign(
            name=form.name,
            niche=form.niche,
            cities=cities,
            target_mobile_leads=form.target_mobile_leads,
            setting_profile_id=form.setting_profile_id,
            default_run_mode=form.default_run_mode,
            database_path=campaign_db_path,
            output_dir=campaign_output_dir,
            notes=form.notes,
        )
        return RedirectResponse(url=f"/campaigns/{campaign.id}", status_code=303)

    @router.get("/campaigns/{campaign_id}", response_class=HTMLResponse)
    def campaign_detail(
        request: Request,
        campaign_id: int,
        campaigns_repo: CampaignRepository = Depends(campaign_repository),
    ) -> HTMLResponse:
        campaign = campaigns_repo.get_campaign(campaign_id)
        if campaign is None:
            raise HTTPException(status_code=404, detail="Campaign not found.")
        cities = campaigns_repo.list_cities(campaign_id)
        recent_runs = campaigns_repo.recent_runs(campaign_id)
        summary = campaigns_repo.campaign_run_summary(campaign_id)
        return templates.TemplateResponse(
            "campaigns/detail.html",
            {
                "request": request,
                "campaign": campaign,
                "cities": cities,
                "recent_runs": recent_runs,
                "summary": summary,
            },
        )

    @router.post("/campaigns/{campaign_id}/runs")
    def start_campaign_run(
        campaign_id: int,
        mode: str = Form(...),
        runs_repo: RunJobRepository = Depends(run_repository),
        campaigns_repo: CampaignRepository = Depends(campaign_repository),
    ) -> RedirectResponse:
        if campaigns_repo.get_campaign(campaign_id) is None:
            raise HTTPException(status_code=404, detail="Campaign not found.")
        if mode not in ALLOWED_RUN_MODES:
            raise HTTPException(status_code=400, detail="Unsupported run mode.")
        run = runs_repo.create_run(campaign_id=campaign_id, mode=mode)
        return RedirectResponse(url=f"/runs/{run.id}/start", status_code=303)

    return router
