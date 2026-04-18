"""Settings profile routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from dashboard.repositories.settings_profiles import SettingProfileRepository
from dashboard.routes.deps import profile_repository
from dashboard.schemas.forms import SettingProfileCreateForm


def build_router(templates: Jinja2Templates) -> APIRouter:
    """Create settings profile router."""
    router = APIRouter()

    @router.get("/settings/profiles", response_class=HTMLResponse)
    def list_profiles(
        request: Request,
        profiles_repo: SettingProfileRepository = Depends(profile_repository),
    ) -> HTMLResponse:
        return templates.TemplateResponse(
            "settings/profiles.html",
            {"request": request, "profiles": profiles_repo.list_profiles()},
        )

    @router.post("/settings/profiles")
    def create_profile(
        name: str = Form(...),
        max_search_results_per_query: int = Form(...),
        max_site_pages_per_company: int = Form(...),
        enrichment_workers: int = Form(...),
        request_delay_ms: int = Form(...),
        site_timeout_sec: int = Form(...),
        profiles_repo: SettingProfileRepository = Depends(profile_repository),
    ) -> RedirectResponse:
        form = SettingProfileCreateForm(
            name=name,
            max_search_results_per_query=max_search_results_per_query,
            max_site_pages_per_company=max_site_pages_per_company,
            enrichment_workers=enrichment_workers,
            request_delay_ms=request_delay_ms,
            site_timeout_sec=site_timeout_sec,
        )
        profiles_repo.create_profile(**form.model_dump())
        return RedirectResponse(url="/settings/profiles", status_code=303)

    return router
