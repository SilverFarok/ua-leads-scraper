"""Website scraper for contact extraction without a browser when possible."""

from __future__ import annotations

import logging
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from requests import Response, Session

from config import Settings
from models import SiteScrapeResult
from utils.phone_utils import extract_phone_candidates
from utils.rate_limiter import RateLimiter
from utils.text_utils import canonicalize_url, is_domain_in_blocklist, normalize_whitespace


class SiteScraper:
    """Scrape websites and contact pages to extract phones."""

    def __init__(self, session: Session, settings: Settings, logger: logging.Logger) -> None:
        self._session = session
        self._settings = settings
        self._logger = logger
        self._rate_limiter = RateLimiter(settings.request_delay_sec)

    def scrape(self, website: str) -> SiteScrapeResult:
        """Fetch the main website page and a small set of contact-like pages."""
        if is_domain_in_blocklist(website, self._settings.blocked_domains):
            self._logger.info("Skipping blacklisted domain: %s", website)
            return SiteScrapeResult(website=website, title=None, phone_candidates=[], visited_urls=[])

        main_response = self._get(website)
        if main_response is None:
            return SiteScrapeResult(website=website, title=None, phone_candidates=[], visited_urls=[])

        soup = BeautifulSoup(main_response.text, "lxml")
        visited_urls = [main_response.url]
        phone_candidates = self._extract_phones_from_soup(soup)
        title = normalize_whitespace(soup.title.get_text(" ", strip=True)) if soup.title else None

        contact_links = self._extract_contact_links(main_response.url, soup)
        for contact_url in contact_links[: max(self._settings.max_site_pages_per_company - 1, 0)]:
            response = self._get(contact_url)
            if response is None:
                continue

            visited_urls.append(response.url)
            page_soup = BeautifulSoup(response.text, "lxml")
            phone_candidates.extend(self._extract_phones_from_soup(page_soup))

        return SiteScrapeResult(
            website=website,
            title=title,
            phone_candidates=list(dict.fromkeys(phone_candidates)),
            visited_urls=visited_urls,
        )

    def _get(self, url: str) -> Response | None:
        """Send GET request with retry-enabled session and timeout."""
        try:
            self._rate_limiter.wait()
            response = self._session.get(url, timeout=self._settings.request_timeout_sec)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or response.encoding or "utf-8"
            return response
        except Exception:
            self._logger.debug("Website request failed: %s", url, exc_info=True)
            return None

    def _extract_phones_from_soup(self, soup: BeautifulSoup) -> list[str]:
        """Extract phones from visible text and tel links."""
        phones: list[str] = []
        visible_text = normalize_whitespace(soup.get_text(" ", strip=True))
        phones.extend(extract_phone_candidates(visible_text))

        for link in soup.select('a[href^="tel:"]'):
            href = link.get("href", "")
            if href:
                phones.append(href.replace("tel:", "").strip())

        return list(dict.fromkeys(item for item in phones if item))

    def _extract_contact_links(self, base_url: str, soup: BeautifulSoup) -> list[str]:
        """Find a small set of internal contact-related links."""
        base_domain = urlparse(base_url).netloc.lower()
        discovered: list[str] = []
        seen: set[str] = set()

        for link in soup.find_all("a", href=True):
            href = link.get("href", "").strip()
            text = normalize_whitespace(link.get_text(" ", strip=True)).lower()
            absolute_url = urljoin(base_url, href)
            if is_domain_in_blocklist(absolute_url, self._settings.blocked_domains):
                continue
            parsed = urlparse(absolute_url)
            if parsed.netloc.lower() != base_domain:
                continue

            candidate = canonicalize_url(absolute_url)
            if not candidate or candidate in seen:
                continue

            url_lower = absolute_url.lower()
            if any(keyword.lower() in url_lower or keyword.lower() in text for keyword in self._settings.contact_path_keywords):
                seen.add(candidate)
                discovered.append(absolute_url)

        return discovered
