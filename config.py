"""Application configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


def _to_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _split_csv_env(value: str | None, default: list[str]) -> tuple[str, ...]:
    if not value:
        return tuple(default)
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _resolve_optional_path(base_dir: Path, value: str | None) -> Path | None:
    """Resolve an optional path-like environment variable against the project root."""
    if not value:
        return None
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = base_dir / candidate
    return candidate


@dataclass(frozen=True, slots=True)
class Settings:
    """Immutable application settings loaded from .env."""

    app_name: str
    base_dir: Path
    data_dir: Path
    output_dir: Path
    log_dir: Path
    input_csv: Path
    database_path: Path
    log_level: str
    request_timeout_sec: int
    request_retries: int
    request_delay_sec: float
    max_search_results_per_query: int
    max_site_pages_per_company: int
    enrichment_workers: int
    target_mobile_leads: int
    blocked_domains: tuple[str, ...]
    google_sheets_enabled: bool
    google_sheets_credentials_path: Path | None
    google_sheets_spreadsheet_id: str | None
    google_sheets_worksheet_prefix: str
    google_sheets_clear_before_write: bool
    playwright_headless: bool
    playwright_timeout_ms: int
    user_agent: str
    ua_mobile_prefixes: tuple[str, ...]
    contact_path_keywords: tuple[str, ...]

    def ensure_directories(self) -> None:
        """Create required local directories if they do not exist."""
        for path in (self.data_dir, self.output_dir, self.log_dir):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load settings once and cache them for the current process."""
    base_dir = Path(__file__).resolve().parent
    load_dotenv(base_dir / ".env")

    data_dir = base_dir / "data"
    output_dir = base_dir / os.getenv("OUTPUT_DIR", "output")
    log_dir = base_dir / os.getenv("LOG_DIR", "logs")

    default_mobile_prefixes = [
        "39",
        "50",
        "63",
        "66",
        "67",
        "68",
        "73",
        "91",
        "92",
        "93",
        "94",
        "95",
        "96",
        "97",
        "98",
        "99",
    ]
    default_contact_keywords = [
        "\u043a\u043e\u043d\u0442\u0430\u043a\u0442",
        "\u043a\u043e\u043d\u0442\u0430\u043a\u0442\u0438",
        "contact",
        "contacts",
        "about",
        "about-us",
        "\u043f\u0440\u043e-\u043d\u0430\u0441",
        "pro-nas",
        "\u0437\u0432\u0027\u044f\u0437\u043e\u043a",
        "zviazok",
    ]

    settings = Settings(
        app_name=os.getenv("APP_NAME", "ua-business-leads-mvp"),
        base_dir=base_dir,
        data_dir=data_dir,
        output_dir=output_dir,
        log_dir=log_dir,
        input_csv=base_dir / os.getenv("INPUT_CSV", "data/input.csv"),
        database_path=base_dir / os.getenv("DATABASE_PATH", "data/leads.sqlite3"),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        request_timeout_sec=int(os.getenv("REQUEST_TIMEOUT_SEC", "20")),
        request_retries=int(os.getenv("REQUEST_RETRIES", "3")),
        request_delay_sec=float(os.getenv("REQUEST_DELAY_SEC", "1.5")),
        max_search_results_per_query=int(os.getenv("MAX_SEARCH_RESULTS_PER_QUERY", "30")),
        max_site_pages_per_company=int(os.getenv("MAX_SITE_PAGES_PER_COMPANY", "3")),
        enrichment_workers=max(int(os.getenv("ENRICHMENT_WORKERS", "5")), 1),
        target_mobile_leads=int(os.getenv("TARGET_MOBILE_LEADS", "0")),
        blocked_domains=_split_csv_env(os.getenv("BLOCKED_DOMAINS"), []),
        google_sheets_enabled=_to_bool(os.getenv("GOOGLE_SHEETS_ENABLED", "false"), default=False),
        google_sheets_credentials_path=_resolve_optional_path(
            base_dir,
            os.getenv("GOOGLE_SHEETS_CREDENTIALS_PATH"),
        ),
        google_sheets_spreadsheet_id=os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID"),
        google_sheets_worksheet_prefix=os.getenv("GOOGLE_SHEETS_WORKSHEET_PREFIX", "results"),
        google_sheets_clear_before_write=_to_bool(
            os.getenv("GOOGLE_SHEETS_CLEAR_BEFORE_WRITE", "true"),
            default=True,
        ),
        playwright_headless=_to_bool(os.getenv("PLAYWRIGHT_HEADLESS", "true"), default=True),
        playwright_timeout_ms=int(os.getenv("PLAYWRIGHT_TIMEOUT_MS", "30000")),
        user_agent=os.getenv(
            "USER_AGENT",
            (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
        ),
        ua_mobile_prefixes=_split_csv_env(os.getenv("UA_MOBILE_PREFIXES"), default_mobile_prefixes),
        contact_path_keywords=_split_csv_env(
            os.getenv("CONTACT_PATH_KEYWORDS"),
            default_contact_keywords,
        ),
    )
    settings.ensure_directories()
    return settings
