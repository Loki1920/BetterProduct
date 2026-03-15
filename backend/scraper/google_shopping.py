"""
Google Shopping scraper — tertiary fallback.
Broadest coverage but highest bot-detection risk.
Uses stealth mode + random delays to reduce blocking.
"""
from __future__ import annotations

import re
from typing import List, Optional
from urllib.parse import quote_plus, urlparse

from bs4 import BeautifulSoup

from backend.models import Platform, ProductData
from backend.scraper.base import BaseScraper
from backend.scraper.duckduckgo_shopping import _store_from_url


class GoogleShoppingScraper(BaseScraper):
    PLATFORM_NAME = "google_shopping"
    BASE_URL = "https://www.google.com"

    async def scrape_product(self, url: str) -> ProductData:
        raise NotImplementedError("GoogleShoppingScraper is search-only")

    async def search(self, query: str, max_results: int = 10) -> List[ProductData]:
        url = f"https://www.google.com/search?q={quote_plus(query)}&tbm=shop&hl=en&gl=us"
        page, html = await self.get_page(url)

        for sel in (".sh-dgr__grid-result", "[data-docid]", ".sh-pr__product-results"):
            try:
                await page.wait_for_selector(sel, timeout=6_000)
                break
            except Exception:
                continue

        html = await page.content()
        await page.close()

        # Check for CAPTCHA / consent page
        if "captcha" in html.lower() or "consent.google" in html.lower():
            return []

        soup = BeautifulSoup(html, "lxml")
        results: List[ProductData] = []

        containers = (
            soup.select(".sh-dgr__grid-result")
            or soup.select("[data-docid]")
            or soup.select(".g")
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
        # Google Shopping uses obfuscated class names that change —
        # rely on element roles and text patterns instead
        title_el = item.select_one("h3, h4, [role='heading']")
        if not title_el:
            return None
        title = title_el.get_text(strip=True)
        if not title:
            return None

        # Price — look for elements containing currency symbols
        price: Optional[float] = None
        currency = "USD"   # resolved after URL is known (see below)
        for el in item.select("span, div"):
            txt = el.get_text(strip=True)
            if re.match(r"^[\$₹£€][\d,]+", txt) or re.match(r"^[\d,]+\.?\d*\s*[\$₹£€]", txt):
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
                        break
                    except Exception:
                        pass

        # Store — usually a small text near the bottom of the card
        store = ""
        for el in item.select("span, div"):
            txt = el.get_text(strip=True)
            # Store names are typically short, don't contain numbers
            if 3 < len(txt) < 40 and not re.search(r"\d", txt) and txt != title:
                store = txt
                break

        # URL
        link = item.select_one("a[href]")
        url = link["href"] if link else ""
        if url.startswith("/url?"):
            # Google wraps URLs — extract real URL
            m2 = re.search(r"[?&]url=([^&]+)", url)
            if m2:
                from urllib.parse import unquote
                url = unquote(m2.group(1))
        if not url or not url.startswith("http"):
            return None
        from backend.scraper.duckduckgo_shopping import _is_product_url
        if not _is_product_url(url):
            return None

        if not store:
            store = _store_from_url(url)

        # If no currency symbol was detected in price text, infer from product URL
        if currency == "USD":
            from backend.scraper.parser import StructuredDataParser
            currency = StructuredDataParser._infer_currency(url)

        # Image
        img_el = item.select_one("img[src]")
        images = []
        if img_el:
            src = img_el.get("src", "")
            if src and not src.startswith("data:"):
                images = [src]

        return ProductData(
            url=url,
            platform=Platform.UNKNOWN,
            title=title,
            price=price,
            currency=currency,
            shipping=0.0,
            total_cost=price,
            seller=store or _store_from_url(url),
            images=images,
        )
