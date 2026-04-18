"""HTML search scraper used as fallback for website discovery."""

from __future__ import annotations

import logging
from urllib.parse import parse_qs, unquote, urlparse

from bs4 import BeautifulSoup
from requests import Session

from config import Settings
from models import CompanyCandidate
from utils.rate_limiter import RateLimiter
from utils.text_utils import is_blocked_directory_url, is_domain_in_blocklist, normalize_whitespace


class SearchScraper:
    """DuckDuckGo HTML scraper for lightweight website discovery."""

    SEARCH_URL = "https://html.duckduckgo.com/html/"

    def __init__(self, session: Session, settings: Settings, logger: logging.Logger) -> None:
        self._session = session
        self._settings = settings
        self._logger = logger
        self._rate_limiter = RateLimiter(settings.request_delay_sec)

    def search_businesses(self, niche: str, city: str) -> list[CompanyCandidate]:
        """Search businesses when Google Maps returns nothing usable."""
        query = f"{niche} {city}".strip()
        results = self._search(query)
        candidates: list[CompanyCandidate] = []
        for result in results[: self._settings.max_search_results_per_query]:
            candidates.append(
                CompanyCandidate(
                    company_name=self._title_to_company_name(result["title"]),
                    city=city,
                    website=result["url"],
                    google_maps_url=None,
                    source="search",
                    phone_candidates=[],
                )
            )
        return candidates

    def find_official_website(self, company_name: str, city: str) -> str | None:
        """Return the most likely official website URL for a company."""
        query = f'"{company_name}" {city} official site'
        results = self._search(query)
        for result in results:
            if not is_blocked_directory_url(result["url"]):
                return result["url"]
        return None

    def _search(self, query: str) -> list[dict[str, str]]:
        """Run a lightweight search and parse result links."""
        self._rate_limiter.wait()
        response = self._session.get(
            self.SEARCH_URL,
            params={"q": query},
            timeout=self._settings.request_timeout_sec,
        )
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding or "utf-8"

        soup = BeautifulSoup(response.text, "lxml")
        parsed_results: list[dict[str, str]] = []
        seen_urls: set[str] = set()

        for link in soup.select("a.result__a"):
            href = link.get("href")
            title = normalize_whitespace(link.get_text(" ", strip=True))
            target_url = self._unwrap_duckduckgo_url(href)
            if not target_url or is_blocked_directory_url(target_url):
                continue
            if is_domain_in_blocklist(target_url, self._settings.blocked_domains):
                continue
            if target_url in seen_urls:
                continue

            seen_urls.add(target_url)
            parsed_results.append({"title": title, "url": target_url})

        self._logger.debug("Search results for '%s': %s", query, len(parsed_results))
        return parsed_results

    def _unwrap_duckduckgo_url(self, href: str | None) -> str | None:
        """Extract target URL from DuckDuckGo redirect links."""
        if not href:
            return None
        if href.startswith("http"):
            return href

        parsed = urlparse(href)
        query = parse_qs(parsed.query)
        target = query.get("uddg", [None])[0]
        if not target:
            return None
        return unquote(target)

    def _title_to_company_name(self, title: str) -> str:
        """Get a usable company name from a search result title."""
        for separator in ("|", " - ", " \u2014 "):
            if separator in title:
                value = title.split(separator)[0].strip()
                if value:
                    return value
        return title or "Unknown company"
