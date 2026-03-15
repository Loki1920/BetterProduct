"""
DuckDuckGo Shopping scraper — returns results from ANY store worldwide.
No API key required. Zero config.
"""
from __future__ import annotations

import re
from typing import List, Optional
from urllib.parse import quote_plus, urlparse

from bs4 import BeautifulSoup

from backend.models import Platform, ProductData
from backend.scraper.base import BaseScraper


from urllib.parse import parse_qs as _parse_qs, urlparse as _urlparse, unquote as _unquote

# Query-string params that indicate a search/listing page
_SEARCH_PARAM_RE = re.compile(
    r"^(q|query|s|k|search|keyword|keywords|searchTerm)$", re.IGNORECASE
)
# Path segments that indicate a search/listing/category page
_SEARCH_PATH_RE = re.compile(
    r"^/(search|browse|category|categories|listing|collections|results|find)(/|$)",
    re.IGNORECASE,
)


def _resolve_ddg_redirect(url: str) -> str:
    """Unwrap DuckDuckGo redirect URLs (duckduckgo.com/l/?uddg=...) to the real URL."""
    try:
        parsed = _urlparse(url)
        if "duckduckgo.com" in parsed.netloc:
            params = _parse_qs(parsed.query)
            real = params.get("uddg", params.get("u3", [None]))[0]
            if real:
                return _unquote(real)
    except Exception:
        pass
    return url


def _is_product_url(url: str) -> bool:
    """Return False only for URLs that are clearly search/listing pages."""
    if not url or not url.startswith("http"):
        return False
    try:
        parsed = _urlparse(url)
        path = parsed.path
        params = _parse_qs(parsed.query)

        # Reject if query string contains a search parameter
        if any(_SEARCH_PARAM_RE.match(k) for k in params):
            return False

        # Reject if the path is a known search/listing route
        if _SEARCH_PATH_RE.match(path):
            return False

        return True
    except Exception:
        return True  # don't drop on parse error


def _store_from_url(url: str) -> str:
    """Derive a readable store name from a URL domain."""
    try:
        domain = urlparse(url).netloc.lower().replace("www.", "")
        # e.g. flipkart.com → Flipkart
        name = domain.split(".")[0]
        return name.title()
    except Exception:
        return "Online Store"


class DuckDuckGoShopping(BaseScraper):
    """
    Search DuckDuckGo Shopping.
    Returns product results from any retailer — Flipkart, Amazon, Croma,
    Myntra, eBay, Walmart, Tata Cliq, etc. — all from one query.
    """

    PLATFORM_NAME = "duckduckgo"
    BASE_URL = "https://duckduckgo.com"

    async def scrape_product(self, url: str) -> ProductData:
        raise NotImplementedError("DuckDuckGoShopping is search-only")

    async def search(self, query: str, max_results: int = 10) -> List[ProductData]:
        url = f"https://duckduckgo.com/?q={quote_plus(query)}&iax=shopping&ia=shopping"
        page, html = await self.get_page(url)

        # Wait for shopping tiles (multiple possible selectors)
        for sel in (".tile--srd", "[data-testid='shopping-result']", ".tile", ".zci--products"):
            try:
                await page.wait_for_selector(sel, timeout=5_000)
                break
            except Exception:
                continue

        html = await page.content()
        await page.close()

        soup = BeautifulSoup(html, "lxml")
        results: List[ProductData] = []

        # DuckDuckGo shopping tile containers — try multiple selector patterns
        containers = (
            soup.select(".tile--srd")
            or soup.select("[data-testid='shopping-result']")
            or soup.select(".zci--products .tile")
            or soup.select(".tile")
        )

        for item in containers:
            try:
                p = self._parse_tile(item)
                if p:
                    results.append(p)
                    if len(results) >= max_results:
                        break
            except Exception:
                continue

        return results

    def _parse_tile(self, item) -> Optional[ProductData]:
        # Title — try common DDG class patterns
        title_el = (
            item.select_one(".tile__title")
            or item.select_one("[class*='title']")
            or item.select_one("a[title]")
        )
        if not title_el:
            return None
        title = title_el.get("title") or title_el.get_text(strip=True)
        if not title:
            return None

        # URL
        link = item.select_one("a[href]")
        url = link["href"] if link else ""
        if not url or url.startswith("//duckduckgo"):
            return None
        url = _resolve_ddg_redirect(url)
        if not _is_product_url(url):
            return None

        # Price
        price: Optional[float] = None
        price_el = (
            item.select_one(".tile__price")
            or item.select_one("[class*='price']")
        )
        if price_el:
            m = re.search(r"[\d,]+\.?\d*", price_el.get_text(strip=True))
            if m:
                try:
                    price = float(m.group().replace(",", ""))
                except Exception:
                    pass

        # Currency — infer from URL, then override with explicit symbol if present
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

        # Store / merchant
        store_el = (
            item.select_one(".tile__merchant")
            or item.select_one("[class*='merchant']")
            or item.select_one("[class*='store']")
            or item.select_one("[class*='seller']")
        )
        store = store_el.get_text(strip=True) if store_el else _store_from_url(url)

        # Image
        img_el = item.select_one("img[src]")
        images = [img_el["src"]] if img_el else []

        return ProductData(
            url=url,
            platform=Platform.UNKNOWN,
            title=title,
            price=price,
            currency=currency,
            shipping=0.0,
            total_cost=price,
            seller=store,
            images=images,
        )
