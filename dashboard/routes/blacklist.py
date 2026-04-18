"""Domain blacklist routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from dashboard.repositories.blacklist import DomainBlacklistRepository
from dashboard.routes.deps import blacklist_repository
from dashboard.schemas.forms import BlacklistCreateForm


def build_router(templates: Jinja2Templates) -> APIRouter:
    """Create blacklist router."""
    router = APIRouter()

    @router.get("/blacklist", response_class=HTMLResponse)
    def list_blacklist(
        request: Request,
        repo: DomainBlacklistRepository = Depends(blacklist_repository),
    ) -> HTMLResponse:
        return templates.TemplateResponse(
            "blacklist/index.html",
            {"request": request, "items": repo.list_domains()},
        )

    @router.post("/blacklist")
    def add_blacklist_item(
        domain: str = Form(...),
        reason: str = Form(""),
        repo: DomainBlacklistRepository = Depends(blacklist_repository),
    ) -> RedirectResponse:
        form = BlacklistCreateForm(domain=domain, reason=reason or None)
        repo.create_domain(form.domain, form.reason)
        return RedirectResponse(url="/blacklist", status_code=303)

    @router.post("/blacklist/{blacklist_id}/delete")
    def delete_blacklist_item(
        blacklist_id: int,
        repo: DomainBlacklistRepository = Depends(blacklist_repository),
    ) -> RedirectResponse:
        repo.delete_domain(blacklist_id)
        return RedirectResponse(url="/blacklist", status_code=303)

    return router
