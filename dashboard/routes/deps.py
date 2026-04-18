"""Route dependency helpers."""

from __future__ import annotations

from fastapi import Request

from dashboard.repositories.blacklist import DomainBlacklistRepository
from dashboard.repositories.campaigns import CampaignRepository
from dashboard.repositories.runs import RunJobRepository
from dashboard.repositories.settings_profiles import SettingProfileRepository


def campaign_repository(request: Request) -> CampaignRepository:
    """Return campaign repository from app state."""
    return request.app.state.campaign_repository


def run_repository(request: Request) -> RunJobRepository:
    """Return run repository from app state."""
    return request.app.state.run_repository


def profile_repository(request: Request) -> SettingProfileRepository:
    """Return profile repository from app state."""
    return request.app.state.profile_repository


def blacklist_repository(request: Request) -> DomainBlacklistRepository:
    """Return blacklist repository from app state."""
    return request.app.state.blacklist_repository
