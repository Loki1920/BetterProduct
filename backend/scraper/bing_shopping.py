"""
Bing Shopping scraper — fallback when DuckDuckGo yields no results.
No API key. Good global + India coverage.
"""
from __future__ import annotations

import re
from typing import List, Optional
from urllib.parse import quote_plus, urljoin, urlparse

from bs4 import BeautifulSoup

from backend.models import Platform, ProductData
from backend.scraper.base import BaseScraper
from backend.scraper.duckduckgo_shopping import _store_from_url


class BingShoppingScraper(BaseScraper):
    PLATFORM_NAME = "bing_shopping"
    BASE_URL = "https://www.bing.com"

    async def scrape_product(self, url: str) -> ProductData:
        raise NotImplementedError("BingShoppingScraper is search-only")

    async def search(self, query: str, max_results: int = 10) -> List[ProductData]:
        url = f"https://www.bing.com/shop?q={quote_plus(query)}&setlang=en-US&cc=US"
        page, html = await self.get_page(url)

        for sel in (".br-item", ".pd-item", ".item", "[class*='item']"):
            try:
                await page.wait_for_selector(sel, timeout=6_000)
                break
            except Exception:
                continue

        html = await page.content()
        await page.close()

        soup = BeautifulSoup(html, "lxml")
        results: List[ProductData] = []

        containers = (
            soup.select(".br-item")
            or soup.select(".pd-item")
            or soup.select("li.item")
        )

        for item in containers:
            try:
                p = self._parse_card(item)
                if p:
                    results.append(p)
                    if len(results) >= max_results:
                        break
            except Exception:
                continue

        return results

    def _parse_card(self, item) -> Optional[ProductData]:
        title_el = (
            item.select_one(".pd-title")
            or item.select_one(".item-title")
            or item.select_one("h3")
            or item.select_one("h2")
            or item.select_one("[class*='title']")
        )
        if not title_el:
            return None
        title = title_el.get_text(strip=True)
        if not title:
            return None

        # URL — Bing wraps links through its redirect; try to get the real href
        link = item.select_one("a[href]")
        raw_url = link["href"] if link else ""
        # Resolve relative URLs
        if raw_url and not raw_url.startswith("http"):
            raw_url = urljoin(self.BASE_URL, raw_url)
        url = raw_url

        # Price
        price: Optional[float] = None
        price_el = (
            item.select_one(".pd-price")
            or item.select_one(".price")
            or item.select_one("[class*='price']")
        )
        # Infer currency from URL first, then override with explicit symbol
        from backend.scraper.parser import StructuredDataParser
        currency = StructuredDataParser._infer_currency(url)
        if price_el:
            txt = price_el.get_text(strip=True)
            if "₹" in txt:
                currency = "INR"
            elif "£" in txt:
                currency = "GBP"
            elif "€" in txt:
                currency = "EUR"
            elif "$" in txt:
                currency = "USD"
            m = re.search(r"[\d,]+\.?\d*", txt)
            if m:
                try:
                    price = float(m.group().replace(",", ""))
                except Exception:
                    pass

        # Store
        store_el = (
            item.select_one(".pd-seller")
            or item.select_one(".merchant")
            or item.select_one("[class*='seller']")
            or item.select_one("[class*='merchant']")
            or item.select_one("[class*='store']")
        )
        store = store_el.get_text(strip=True) if store_el else _store_from_url(url)

        # Rating
        rating: Optional[float] = None
        rating_el = item.select_one("[class*='rating'], [aria-label*='star']")
        if rating_el:
            m2 = re.search(r"[\d.]+", rating_el.get("aria-label", "") or rating_el.get_text())
            if m2:
                try:
                    rating = float(m2.group())
                except Exception:
                    pass

        # Image
        img_el = item.select_one("img[src]")
        images = [img_el["src"]] if img_el else []

        if not title or not url:
            return None
        from backend.scraper.duckduckgo_shopping import _is_product_url
        if not _is_product_url(url):
            return None

        return ProductData(
            url=url,
            platform=Platform.UNKNOWN,
            title=title,
            price=price,
            currency=currency,
            shipping=0.0,
            total_cost=price,
            seller=store,
            rating=rating,
            images=images,
        )
