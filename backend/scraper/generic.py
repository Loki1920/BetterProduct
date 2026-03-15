from __future__ import annotations

from typing import List
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from backend.models import Platform, ProductData
from backend.scraper.base import BaseScraper
from backend.scraper.parser import StructuredDataParser


class GenericScraper(BaseScraper):
    """Fallback scraper for unknown platforms — relies entirely on structured data."""

    PLATFORM_NAME = "unknown"

    async def scrape_product(self, url: str) -> ProductData:
        page, html = await self.get_page(url)
        soup = BeautifulSoup(html, "lxml")
        sd = StructuredDataParser.extract(html, url)

        title = sd.get("title") or ""
        if not title:
            title_tag = soup.find("title")
            title = title_tag.get_text(strip=True) if title_tag else "Unknown"

        await page.close()
        return ProductData(
            url=url,
            platform=Platform.UNKNOWN,
            title=title,
            price=sd.get("price"),
            brand=sd.get("brand") or None,
            model_number=sd.get("model_number") or None,
            gtin=sd.get("gtin") or None,
            sku=sd.get("sku") or None,
            rating=sd.get("rating"),
            review_count=sd.get("review_count"),
            specs=sd.get("specs", {}),
            images=sd.get("images", []),
            description=sd.get("description", ""),
            availability=sd.get("availability"),
        )

    async def search(self, query: str, max_results: int = 5) -> List[ProductData]:
        return []
