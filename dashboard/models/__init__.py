"""Dashboard admin models."""

from dashboard.models.blacklist import DomainBlacklistRecord
from dashboard.models.campaign import CampaignCityRecord, CampaignRecord
from dashboard.models.run_job import RunJobRecord
from dashboard.models.setting_profile import SettingProfileRecord

__all__ = [
    "CampaignCityRecord",
    "CampaignRecord",
    "DomainBlacklistRecord",
    "RunJobRecord",
    "SettingProfileRecord",
]
