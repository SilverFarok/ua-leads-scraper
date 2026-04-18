"""Text and URL normalization helpers."""

from __future__ import annotations

import re
from urllib.parse import urlparse


BLOCKED_DOMAINS = {
    "facebook.com",
    "www.facebook.com",
    "instagram.com",
    "www.instagram.com",
    "linkedin.com",
    "www.linkedin.com",
    "youtube.com",
    "www.youtube.com",
    "t.me",
    "telegram.me",
    "maps.google.com",
    "www.google.com",
    "google.com",
    "g.co",
    "2gis.ua",
    "2gis.com",
    "flagma.ua",
    "work.ua",
    "ua-region.com.ua",
}


def normalize_whitespace(value: str) -> str:
    """Collapse internal whitespace to single spaces."""
    return re.sub(r"\s+", " ", value or "").strip()


def canonicalize_url(url: str | None) -> str | None:
    """Build a stable comparable website key."""
    if not url:
        return None
    parsed = urlparse(url.strip())
    if not parsed.scheme and not parsed.netloc:
        parsed = urlparse(f"https://{url.strip()}")

    hostname = (parsed.netloc or "").lower().replace("www.", "")
    if not hostname:
        return None

    path = parsed.path.rstrip("/")
    if path in {"", "/"}:
        return hostname
    return f"{hostname}{path}"


def normalize_name_city_key(company_name: str, city: str) -> str:
    """Create a normalized name+city comparison key."""
    name = normalize_whitespace(company_name).lower()
    city_value = normalize_whitespace(city).lower()
    return f"{name}|{city_value}"


def is_blocked_directory_url(url: str) -> bool:
    """Filter social networks, maps, and known directory-heavy domains."""
    parsed = urlparse(url)
    hostname = parsed.netloc.lower().replace("www.", "")
    normalized_blocked = {domain.replace("www.", "") for domain in BLOCKED_DOMAINS}
    return hostname in normalized_blocked


def is_domain_in_blocklist(url: str, blocked_domains: tuple[str, ...] | list[str]) -> bool:
    """Return True when the URL hostname matches a configured blocked domain."""
    if not blocked_domains:
        return False
    parsed = urlparse(url)
    hostname = parsed.netloc.lower().replace("www.", "")
    normalized_blocked = {domain.strip().lower().replace("www.", "") for domain in blocked_domains if domain.strip()}
    return hostname in normalized_blocked
