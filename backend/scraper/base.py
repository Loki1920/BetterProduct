from __future__ import annotations

import asyncio
import random
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    async_playwright,
)

from backend.models import ProductData


class BaseScraper(ABC):
    """Abstract base for all platform scrapers. Use as async context manager."""

    PLATFORM_NAME: str = "unknown"
    BASE_URL: str = ""

    def __init__(self, timeout: int = 30_000, headless: bool = True):
        self.timeout = timeout
        self.headless = headless
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None

    async def __aenter__(self) -> "BaseScraper":
        await self._start()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self._stop()

    # ------------------------------------------------------------------
    async def _start(self) -> None:
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )
        self._context = await self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
        # Mask webdriver flag
        await self._context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

    async def _stop(self) -> None:
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    # ------------------------------------------------------------------
    async def get_page(self, url: str, wait_selector: Optional[str] = None) -> Tuple[Page, str]:
        """Navigate to URL; return (page, html). Caller must close the page."""
        assert self._context is not None, "Scraper not started — use 'async with'"
        page = await self._context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=self.timeout)
            if wait_selector:
                try:
                    await page.wait_for_selector(wait_selector, timeout=5_000)
                except Exception:
                    pass
            # Random human-like delay
            await asyncio.sleep(random.uniform(0.8, 2.0))
            html = await page.content()
            return page, html
        except Exception:
            await page.close()
            raise

    # ------------------------------------------------------------------
    @abstractmethod
    async def scrape_product(self, url: str) -> ProductData:
        """Scrape a product page and return normalised ProductData."""

    @abstractmethod
    async def search(self, query: str, max_results: int = 5) -> List[ProductData]:
        """Search the platform and return a list of ProductData results."""
