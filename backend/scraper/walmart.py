from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup

from backend.models import Platform, ProductData
from backend.scraper.base import BaseScraper
from backend.scraper.parser import StructuredDataParser


class WalmartScraper(BaseScraper):
    PLATFORM_NAME = "walmart"
    BASE_URL = "https://www.walmart.com"

    async def scrape_product(self, url: str) -> ProductData:
        page, html = await self.get_page(url, wait_selector="[itemprop='name'], h1")
        html = await page.content()
        soup = BeautifulSoup(html, "lxml")
        sd = StructuredDataParser.extract(html, url)

        next_product = self._next_data(soup)
        if next_product:
            await page.close()
            return self._from_next_data(url, next_product, sd)

        title = sd.get("title") or self._text(soup, "h1[itemprop='name'], h1.prod-ProductTitle")
        price = sd.get("price") or self._price(soup)
        brand = sd.get("brand") or self._text(soup, "[itemprop='brand']")

        item_m = re.search(r"/ip/[^/]+/(\d+)", url)
        sku = item_m.group(1) if item_m else None

        specs: dict = {}
        for row in soup.select(".product-specification-section .table-row"):
            k = row.select_one(".attribute")
            v = row.select_one(".value")
            if k and v:
                specs[k.get_text(strip=True)] = v.get_text(strip=True)

        total = price if price else None
        await page.close()
        return ProductData(
            url=url,
            platform=Platform.WALMART,
            title=title or "Unknown",
            price=price,
            shipping=0.0,
            total_cost=total,
            brand=brand or None,
            sku=sku,
            specs=specs,
            rating=sd.get("rating"),
            review_count=sd.get("review_count"),
            seller="Walmart",
        )

    async def search(self, query: str, max_results: int = 5) -> List[ProductData]:
        url = f"{self.BASE_URL}/search?q={quote_plus(query)}"
        page, html = await self.get_page(url)
        try:
            await page.wait_for_selector("[data-item-id]", timeout=6_000)
            html = await page.content()
        except Exception:
            pass
        soup = BeautifulSoup(html, "lxml")

        results: List[ProductData] = []
        for item in soup.select("[data-item-id]"):
            try:
                p = self._parse_result(item)
                if p:
                    results.append(p)
                    if len(results) >= max_results:
                        break
            except Exception:
                continue

        await page.close()
        return results

    # ------------------------------------------------------------------
    def _next_data(self, soup: BeautifulSoup) -> Optional[Dict]:
        script = soup.find("script", id="__NEXT_DATA__")
        if not script:
            return None
        try:
            data = json.loads(script.string or "")
            return (
                data.get("props", {})
                .get("pageProps", {})
                .get("initialData", {})
                .get("data", {})
                .get("product", None)
            )
        except Exception:
            return None

    def _from_next_data(self, url: str, pd: Dict, sd: Dict) -> ProductData:
        title = pd.get("name") or sd.get("title") or "Unknown"
        brand_obj: Any = pd.get("brand", {})
        brand = brand_obj.get("name") if isinstance(brand_obj, dict) else str(brand_obj or "")

        price: Optional[float] = None
        try:
            price = float(pd.get("priceInfo", {}).get("currentPrice", {}).get("price", 0))
        except Exception:
            price = sd.get("price")

        specs: Dict[str, str] = {}
        for group in pd.get("specifications", []):
            for spec in group.get("specifications", []):
                specs[spec.get("name", "")] = spec.get("value", "")

        return ProductData(
            url=url,
            platform=Platform.WALMART,
            title=title,
            price=price,
            shipping=0.0,
            total_cost=price,
            brand=brand or None,
            model_number=pd.get("model") or None,
            sku=pd.get("usItemId") or None,
            gtin=pd.get("upc") or None,
            rating=float(pd["averageRating"]) if pd.get("averageRating") else None,
            review_count=int(pd["numberOfReviews"]) if pd.get("numberOfReviews") else None,
            seller="Walmart",
            specs=specs,
        )

    def _parse_result(self, item) -> Optional[ProductData]:
        item_id = item.get("data-item-id", "")
        title_el = item.select_one("[data-automation-id='product-title']")
        if not title_el:
            return None
        title = title_el.get_text(strip=True)

        link = item.select_one("a")
        url = urljoin(self.BASE_URL, link["href"]) if link else ""

        price: Optional[float] = None
        price_el = item.select_one("[itemprop='price']")
        if price_el:
            try:
                price = float(price_el.get("content", 0))
            except Exception:
                pass
        if price is None:
            for sel in ("[class*='price']",):
                el = item.select_one(sel)
                if el:
                    m = re.search(r"[\d,]+\.?\d*", el.get_text(strip=True))
                    if m:
                        try:
                            price = float(m.group().replace(",", ""))
                            break
                        except Exception:
                            pass

        return ProductData(
            url=url,
            platform=Platform.WALMART,
            title=title,
            price=price,
            shipping=0.0,
            total_cost=price,
            sku=item_id or None,
            seller="Walmart",
        )

    @staticmethod
    def _price(soup: BeautifulSoup) -> Optional[float]:
        for sel in ("[itemprop='price']", ".price-characteristic"):
            el = soup.select_one(sel)
            if el:
                content = el.get("content") or el.get_text(strip=True)
                m = re.search(r"[\d,]+\.?\d*", content)
                if m:
                    try:
                        return float(m.group().replace(",", ""))
                    except Exception:
                        continue
        return None

    @staticmethod
    def _text(soup: BeautifulSoup, selector: str) -> str:
        el = soup.select_one(selector)
        return el.get_text(strip=True) if el else ""
