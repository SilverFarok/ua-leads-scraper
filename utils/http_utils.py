"""HTTP client helpers with retry support."""

from __future__ import annotations

from requests import Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import Settings


def build_retry_session(settings: Settings) -> Session:
    """Create a requests session with retry and a stable user-agent."""
    retry = Retry(
        total=settings.request_retries,
        connect=settings.request_retries,
        read=settings.request_retries,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "HEAD"}),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)

    session = Session()
    session.headers.update(
        {
            "User-Agent": settings.user_agent,
            "Accept-Language": "uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7",
        }
    )
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session
