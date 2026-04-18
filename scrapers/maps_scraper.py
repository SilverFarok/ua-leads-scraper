"""Google Maps scraper via Playwright."""

from __future__ import annotations

import logging
import re
from types import TracebackType
from urllib.parse import quote

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

from config import Settings
from models import CompanyCandidate
from utils.phone_utils import extract_phone_candidates
from utils.rate_limiter import RateLimiter
from utils.text_utils import normalize_whitespace


class GoogleMapsScraper:
    """Best-effort Google Maps scraper."""

    GOOGLE_MAPS_SEARCH_URL = "https://www.google.com/maps/search/{query}"

    def __init__(self, settings: Settings, logger: logging.Logger) -> None:
        self._settings = settings
        self._logger = logger
        self._rate_limiter = RateLimiter(settings.request_delay_sec)
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    def __enter__(self) -> "GoogleMapsScraper":
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self._settings.playwright_headless)
        self._context = self._browser.new_context(
            locale="uk-UA",
            user_agent=self._settings.user_agent,
            viewport={"width": 1440, "height": 1024},
        )
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self._context:
            self._context.close()
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()

    def search(self, niche: str, city: str) -> list[CompanyCandidate]:
        """Search businesses in Google Maps for a niche-city pair."""
        if not self._context:
            raise RuntimeError("GoogleMapsScraper must be used as a context manager.")

        query = f"{niche} {city}".strip()
        url = self.GOOGLE_MAPS_SEARCH_URL.format(query=quote(query))
        self._logger.info("Google Maps query: %s", query)

        page = self._context.new_page()
        try:
            self._rate_limiter.wait()
            page.goto(url, wait_until="domcontentloaded", timeout=self._settings.playwright_timeout_ms)
            page.wait_for_timeout(2500)
            self._dismiss_dialogs(page)
            self._scroll_results(page)
            place_urls = self._extract_place_urls(page)
            if not place_urls and "/place/" in page.url:
                place_urls = [page.url]

            candidates: list[CompanyCandidate] = []
            for place_url in place_urls[: self._settings.max_search_results_per_query]:
                candidate = self._scrape_place(place_url, city)
                if candidate:
                    candidates.append(candidate)
            return candidates
        finally:
            page.close()

    def _dismiss_dialogs(self, page: Page) -> None:
        """Try to remove common consent or modal overlays."""
        selectors = [
            "button[aria-label='\u041f\u0440\u0438\u0439\u043d\u044f\u0442\u0438 \u0432\u0441\u0435']",
            "button[aria-label='Accept all']",
            "button[aria-label='\u0412\u0456\u0434\u0445\u0438\u043b\u0438\u0442\u0438 \u0432\u0441\u0435']",
            "button[aria-label='Reject all']",
        ]
        for selector in selectors:
            try:
                locator = page.locator(selector)
                if locator.count() > 0:
                    locator.first.click(timeout=1500)
                    page.wait_for_timeout(1000)
                    return
            except Exception:
                continue

    def _scroll_results(self, page: Page) -> None:
        """Scroll the maps result feed to expose more results."""
        try:
            feed = page.locator('div[role="feed"]').first
            if feed.count() == 0:
                return

            for _ in range(5):
                feed.evaluate("(element) => { element.scrollTop = element.scrollHeight; }")
                page.wait_for_timeout(1200)
        except Exception:
            self._logger.debug("Maps feed scrolling was skipped.", exc_info=True)

    def _extract_place_urls(self, page: Page) -> list[str]:
        """Collect unique place URLs from the results page."""
        try:
            urls = page.locator('a[href*="/place/"]').evaluate_all(
                "(elements) => elements.map((element) => element.href).filter(Boolean)"
            )
        except Exception:
            return []

        unique_urls: list[str] = []
        seen: set[str] = set()
        for url in urls:
            cleaned = str(url).split("&")[0]
            if cleaned not in seen:
                seen.add(cleaned)
                unique_urls.append(cleaned)
        return unique_urls

    def _scrape_place(self, place_url: str, fallback_city: str) -> CompanyCandidate | None:
        """Open a place page and extract business details."""
        if not self._context:
            return None

        detail_page = self._context.new_page()
        try:
            self._rate_limiter.wait()
            detail_page.goto(
                place_url,
                wait_until="domcontentloaded",
                timeout=self._settings.playwright_timeout_ms,
            )
            detail_page.wait_for_timeout(2200)

            name = self._first_text(detail_page, ["h1", "h1 span"])
            website = self._first_href(
                detail_page,
                [
                    'a[data-item-id="authority"]',
                    'a[aria-label*="Website"]',
                    'a[aria-label*="\u0412\u0435\u0431\u0441\u0430\u0439\u0442"]',
                ],
            )
            body_text = self._page_text(detail_page)
            phone_candidates = extract_phone_candidates(body_text)
            tel_links = detail_page.locator('a[href^="tel:"]').evaluate_all(
                "(elements) => elements.map((element) => element.getAttribute('href'))"
            )
            phone_candidates.extend(link.replace("tel:", "") for link in tel_links if link)

            return CompanyCandidate(
                company_name=name or self._name_from_title(detail_page.title()),
                city=fallback_city,
                website=website,
                google_maps_url=detail_page.url,
                source="maps",
                phone_candidates=list(dict.fromkeys(phone_candidates)),
            )
        except Exception:
            self._logger.debug("Failed to scrape place: %s", place_url, exc_info=True)
            return None
        finally:
            detail_page.close()

    def _first_text(self, page: Page, selectors: list[str]) -> str:
        """Return first non-empty text from the selector list."""
        for selector in selectors:
            try:
                locator = page.locator(selector)
                if locator.count() > 0:
                    text = locator.first.inner_text(timeout=1500).strip()
                    if text:
                        return normalize_whitespace(text)
            except Exception:
                continue
        return ""

    def _first_href(self, page: Page, selectors: list[str]) -> str | None:
        """Return first non-empty href from the selector list."""
        for selector in selectors:
            try:
                locator = page.locator(selector)
                if locator.count() > 0:
                    href = locator.first.get_attribute("href", timeout=1500)
                    if href:
                        return href
            except Exception:
                continue
        return None

    def _page_text(self, page: Page) -> str:
        """Extract page text with a safe fallback."""
        try:
            text = page.locator("body").inner_text(timeout=4000)
        except Exception:
            return ""
        return normalize_whitespace(text)

    def _name_from_title(self, title: str) -> str:
        """Build a fallback company name from the browser title."""
        cleaned = normalize_whitespace(re.sub(r"\s+-\s+Google Maps.*$", "", title))
        return cleaned or "Unknown company"
