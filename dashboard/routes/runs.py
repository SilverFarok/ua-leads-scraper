"""Run routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from dashboard.repositories.campaigns import CampaignRepository
from dashboard.repositories.runs import RunJobRepository
from dashboard.routes.deps import campaign_repository, run_repository
from dashboard.services.view_models import format_duration


def build_router(templates: Jinja2Templates) -> APIRouter:
    """Create run router."""
    router = APIRouter()

    @router.get("/runs", response_class=HTMLResponse)
    def list_runs(
        request: Request,
        runs_repo: RunJobRepository = Depends(run_repository),
    ) -> HTMLResponse:
        return templates.TemplateResponse(
            "runs/list.html",
            {"request": request, "runs": runs_repo.list_runs(), "format_duration": format_duration},
        )

    @router.get("/runs/{run_id}/start")
    def trigger_run(
        request: Request,
        run_id: int,
        runs_repo: RunJobRepository = Depends(run_repository),
    ) -> RedirectResponse:
        run = runs_repo.get_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found.")
        request.app.state.job_manager.start_run(run_id)
        return RedirectResponse(url=f"/runs/{run_id}", status_code=303)

    @router.get("/runs/{run_id}", response_class=HTMLResponse)
    def run_detail(
        request: Request,
        run_id: int,
        runs_repo: RunJobRepository = Depends(run_repository),
        campaigns_repo: CampaignRepository = Depends(campaign_repository),
    ) -> HTMLResponse:
        run = runs_repo.get_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found.")
        campaign = campaigns_repo.get_campaign(run.campaign_id)
        return templates.TemplateResponse(
            "runs/detail.html",
            {
                "request": request,
                "run": run,
                "campaign": campaign,
                "format_duration": format_duration,
            },
        )

    @router.get("/runs/{run_id}/status", response_class=HTMLResponse)
    def run_status_partial(
        request: Request,
        run_id: int,
        runs_repo: RunJobRepository = Depends(run_repository),
    ) -> HTMLResponse:
        run = runs_repo.get_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found.")
        return templates.TemplateResponse(
            "runs/_status.html",
            {"request": request, "run": run, "format_duration": format_duration},
        )

    return router
