"""Google Sheets export helpers."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from config import Settings
from exporters.excel_exporter import ExcelExporter
from models import BusinessLead

try:
    import gspread
except ImportError:  # pragma: no cover - depends on optional runtime package installation
    gspread = None


@dataclass(frozen=True, slots=True)
class GoogleSheetsExportResult:
    """Information about uploaded worksheets."""

    spreadsheet_url: str
    full_worksheet_title: str
    mobile_worksheet_title: str
    full_rows: int
    mobile_rows: int


class GoogleSheetsExporter:
    """Push leads into a configured Google Spreadsheet."""

    def __init__(self, settings: Settings, logger: logging.Logger) -> None:
        self._settings = settings
        self._logger = logger

    def is_configured(self) -> bool:
        """Return True when Google Sheets export is fully configured."""
        credentials_path = self._settings.google_sheets_credentials_path
        return bool(
            gspread is not None
            and self._settings.google_sheets_enabled
            and self._settings.google_sheets_spreadsheet_id
            and credentials_path
            and credentials_path.exists()
        )

    def export(self, leads: list[BusinessLead]) -> GoogleSheetsExportResult | None:
        """Upload full and mobile-only dataframes into Google Sheets."""
        if not self.is_configured():
            if self._settings.google_sheets_enabled and gspread is None:
                self._logger.warning(
                    "Google Sheets export is enabled but 'gspread' is not installed. Run 'pip install -r requirements.txt'."
                )
            else:
                self._logger.info("Google Sheets export is disabled or not fully configured. Skipping.")
            return None

        dataframe = ExcelExporter.build_dataframe(leads)
        mobile_dataframe = dataframe[dataframe["phone_type"] == "mobile"].copy()

        credentials_path = self._settings.google_sheets_credentials_path
        assert credentials_path is not None
        assert gspread is not None

        client = gspread.service_account(filename=str(credentials_path))
        spreadsheet = client.open_by_key(self._settings.google_sheets_spreadsheet_id)

        full_title = self._worksheet_title("full")
        mobile_title = self._worksheet_title("mobile")
        self._write_dataframe(
            spreadsheet=spreadsheet,
            worksheet_title=full_title,
            rows=[dataframe.columns.tolist(), *dataframe.fillna("").values.tolist()],
        )
        self._write_dataframe(
            spreadsheet=spreadsheet,
            worksheet_title=mobile_title,
            rows=[mobile_dataframe.columns.tolist(), *mobile_dataframe.fillna("").values.tolist()],
        )

        return GoogleSheetsExportResult(
            spreadsheet_url=f"https://docs.google.com/spreadsheets/d/{spreadsheet.id}/edit",
            full_worksheet_title=full_title,
            mobile_worksheet_title=mobile_title,
            full_rows=len(dataframe),
            mobile_rows=len(mobile_dataframe),
        )

    def _write_dataframe(
        self,
        *,
        spreadsheet: gspread.Spreadsheet,
        worksheet_title: str,
        rows: list[list[object]],
    ) -> None:
        """Create or reuse a worksheet and write all rows into it."""
        worksheet = self._get_or_create_worksheet(
            spreadsheet=spreadsheet,
            worksheet_title=worksheet_title,
            rows=max(len(rows), 1),
            cols=max(len(rows[0]) if rows else 1, 1),
        )

        if self._settings.google_sheets_clear_before_write:
            worksheet.clear()

        worksheet.update("A1", rows, value_input_option="RAW")

    def _get_or_create_worksheet(
        self,
        *,
        spreadsheet: gspread.Spreadsheet,
        worksheet_title: str,
        rows: int,
        cols: int,
    ) -> gspread.Worksheet:
        """Open an existing worksheet or create one with enough size."""
        try:
            worksheet = spreadsheet.worksheet(worksheet_title)
            worksheet.resize(rows=max(rows, 1), cols=max(cols, 1))
            return worksheet
        except gspread.WorksheetNotFound:
            return spreadsheet.add_worksheet(
                title=worksheet_title,
                rows=max(rows, 1),
                cols=max(cols, 1),
            )

    def _worksheet_title(self, suffix: str) -> str:
        """Build a Google Sheets-safe worksheet title."""
        raw = f"{self._settings.google_sheets_worksheet_prefix}_{suffix}"
        safe = re.sub(r"[\[\]\*\?/\\:]", "_", raw).strip()
        return safe[:100] or f"results_{suffix}"
