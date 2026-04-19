"""Combined export orchestration for XLSX and Google Sheets."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from config import Settings
from exporters.excel_exporter import ExcelExporter
from exporters.google_sheets_exporter import GoogleSheetsExportResult, GoogleSheetsExporter
from models import BusinessLead


@dataclass(frozen=True, slots=True)
class ExportArtifacts:
    """Export results across all enabled sinks."""

    full_excel_path: Path
    mobile_excel_path: Path
    google_sheets: GoogleSheetsExportResult | None


class LeadExportService:
    """Run all configured export targets for a lead list."""

    def __init__(self, settings: Settings, logger: logging.Logger) -> None:
        self._logger = logger
        self._excel_exporter = ExcelExporter(settings)
        self._google_sheets_exporter = GoogleSheetsExporter(settings, logger)

    def export(self, leads: list[BusinessLead]) -> ExportArtifacts:
        """Export to XLSX and optionally to Google Sheets."""
        full_excel_path, mobile_excel_path = self._excel_exporter.export(leads)
        google_sheets_result = self._google_sheets_exporter.export(leads)
        if google_sheets_result is not None:
            self._logger.info(
                "Google Sheets export complete. Spreadsheet: %s | full worksheet: %s (%s rows) | mobile worksheet: %s (%s rows)",
                google_sheets_result.spreadsheet_url,
                google_sheets_result.full_worksheet_title,
                google_sheets_result.full_rows,
                google_sheets_result.mobile_worksheet_title,
                google_sheets_result.mobile_rows,
            )
        return ExportArtifacts(
            full_excel_path=full_excel_path,
            mobile_excel_path=mobile_excel_path,
            google_sheets=google_sheets_result,
        )
