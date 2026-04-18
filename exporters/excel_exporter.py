"""XLSX export helpers."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import pandas as pd

from config import Settings
from models import BusinessLead


class ExcelExporter:
    """Export leads to XLSX files."""

    EXPORT_COLUMNS = [
        "query_niche",
        "query_city",
        "company_name",
        "city",
        "website",
        "google_maps_url",
        "phone_raw",
        "phone_normalized",
        "phone_type",
        "source",
        "created_at",
    ]

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def export(self, leads: list[BusinessLead]) -> tuple[Path, Path]:
        """Export all leads and a mobile-only subset."""
        full_path = self._settings.output_dir / "full_results.xlsx"
        mobile_path = self._settings.output_dir / "mobile_only.xlsx"

        records = [self._serialize_lead(lead) for lead in leads]
        dataframe = pd.DataFrame(records)

        if dataframe.empty:
            dataframe = pd.DataFrame(columns=self.EXPORT_COLUMNS)
        else:
            dataframe = dataframe.reindex(columns=self.EXPORT_COLUMNS)

        dataframe.sort_values(
            by=["query_city", "company_name", "phone_normalized"],
            ascending=[True, True, True],
            inplace=True,
            na_position="last",
        )

        mobile_dataframe = dataframe[dataframe["phone_type"] == "mobile"].copy()

        dataframe.to_excel(full_path, index=False)
        mobile_dataframe.to_excel(mobile_path, index=False)
        return full_path, mobile_path

    def _serialize_lead(self, lead: BusinessLead) -> dict[str, object]:
        """Convert a lead to an Excel-safe record."""
        record = asdict(lead)
        created_at = record.get("created_at")
        if isinstance(created_at, datetime):
            record["created_at"] = created_at.isoformat()
        return record
