"""Pydantic form schemas used by route handlers."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CampaignCreateForm(BaseModel):
    """Validated campaign form payload."""

    name: str = Field(min_length=1, max_length=255)
    niche: str = Field(min_length=1, max_length=255)
    cities_text: str = Field(min_length=1)
    target_mobile_leads: int = Field(ge=0)
    setting_profile_id: int = Field(ge=1)
    default_run_mode: str
    notes: str | None = None


class SettingProfileCreateForm(BaseModel):
    """Validated setting profile form payload."""

    name: str = Field(min_length=1, max_length=255)
    max_search_results_per_query: int = Field(ge=1, le=200)
    max_site_pages_per_company: int = Field(ge=1, le=50)
    enrichment_workers: int = Field(ge=1, le=20)
    request_delay_ms: int = Field(ge=0, le=10000)
    site_timeout_sec: int = Field(ge=5, le=120)


class BlacklistCreateForm(BaseModel):
    """Validated blacklist form payload."""

    domain: str = Field(min_length=1, max_length=255)
    reason: str | None = None
