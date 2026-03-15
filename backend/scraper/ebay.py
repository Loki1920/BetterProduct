from __future__ import annotations

import re
from typing import List, Optional
from urllib.parse import quote_plus, urlparse, parse_qs

from bs4 import BeautifulSoup

from backend.models import Platform, ProductData
from backend.scraper.base import BaseScraper
from backend.scraper.parser import StructuredDataParser


class EbayScraper(BaseScraper):
    PLATFORM_NAME = "ebay"
    BASE_URL = "https://www.ebay.com"

    @staticmethod
    def _resolve_url(url: str) -> str:
        """
        Convert eBay catalog/product-group URLs to a standard item URL.

        Formats handled:
          /p/<pgid>?iid=<item_id>   → /itm/<item_id>
          /p/<pgid>                 → keep as-is (catalog page, scrape directly)
          /itm/<item_id>            → unchanged
        """
        parsed = urlparse(url)
        # /p/<pgid>?iid=<item_id>
        if parsed.path.startswith("/p/"):
            qs = parse_qs(parsed.query)
            iid_list = qs.get("iid", [])
            if iid_list:
                return f"https://www.ebay.com/itm/{iid_list[0]}"
        return url

    async def scrape_product(self, url: str) -> ProductData:
        # Resolve catalog URLs to item URLs before scraping
        resolved_url = self._resolve_url(url)

        page, html = await self.get_page(resolved_url)
        soup = BeautifulSoup(html, "lxml")
        sd = StructuredDataParser.extract(html, resolved_url)

        # Try multiple title selectors to handle both /itm/ and /p/ page layouts
        title = (
            sd.get("title")
            or self._text(soup, "h1.x-item-title__mainTitle span")
            or self._text(soup, "h1.it-ttl")
            or self._text(soup, "h1[itemprop='name']")
            or self._text(soup, "h1")
        )

        price = sd.get("price") or self._price(soup)

        shipping = 0.0
        ship_el = soup.select_one(".ux-labels-values--shipping .ux-textspans--BOLD")
        if ship_el:
            ship_txt = ship_el.get_text(strip=True).lower()
            if "free" not in ship_txt:
                try:
                    shipping = float(re.sub(r"[^\d.]", "", ship_txt))
                except Exception:
                    pass

        specs: dict = {}
        for row in soup.select(".ux-layout-section-evo__item"):
            label = row.select_one(".ux-labels-values__labels")
            value = row.select_one(".ux-labels-values__values")
            if label and value:
                specs[label.get_text(strip=True)] = value.get_text(strip=True)

        brand = sd.get("brand") or specs.get("Brand", "")
        model = sd.get("model_number") or specs.get("Model", "")
        gtin = sd.get("gtin") or specs.get("UPC", "") or specs.get("EAN", "")

        seller = self._text(soup, ".x-sellercard-atf__info__about-seller a")

        # Extract item ID from resolved URL (may be /itm/ now)
        item_m = re.search(r"/itm/(\d+)", resolved_url)
        # Fallback: try iid query param from original URL
        if not item_m:
            qs = parse_qs(urlparse(url).query)
            iid_list = qs.get("iid", [])
            sku = iid_list[0] if iid_list else None
        else:
            sku = item_m.group(1)

        images = sd.get("images", [])
        total = (price or 0) + shipping

        await page.close()
        return ProductData(
            url=url,
            platform=Platform.EBAY,
            title=title or "Unknown",
            price=price,
            currency="USD",
            shipping=shipping,
            total_cost=total if price else None,
            brand=brand or None,
            model_number=model or None,
            gtin=gtin or None,
            sku=sku,
            rating=sd.get("rating"),
            review_count=sd.get("review_count"),
            seller=seller or "eBay Seller",
            specs=specs,
            images=images,
        )

    async def search(self, query: str, max_results: int = 5) -> List[ProductData]:
        url = f"{self.BASE_URL}/sch/i.html?_nkw={quote_plus(query)}&_sop=15"
        page, html = await self.get_page(url)
        soup = BeautifulSoup(html, "lxml")

        results: List[ProductData] = []
        for item in soup.select(".s-item:not(.s-item--placeholder)"):
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

    def _parse_result(self, item) -> Optional[ProductData]:
        title_el = item.select_one(".s-item__title")
        if not title_el or "Shop on eBay" in title_el.text:
            return None
        title = title_el.get_text(strip=True)

        link = item.select_one(".s-item__link")
        url = link["href"] if link else ""

        price: Optional[float] = None
        price_el = item.select_one(".s-item__price")
        if price_el:
            m = re.search(r"[\d,]+\.?\d*", price_el.get_text(strip=True))
            if m:
                try:
                    price = float(m.group().replace(",", ""))
                except Exception:
                    pass

        shipping = 0.0
        ship_el = item.select_one(".s-item__shipping")
        if ship_el:
            ship_txt = ship_el.get_text(strip=True).lower()
            if "free" not in ship_txt:
                m2 = re.search(r"\+\s*\$?([\d.]+)", ship_txt)
                if m2:
                    try:
                        shipping = float(m2.group(1))
                    except Exception:
                        pass

        item_m = re.search(r"/itm/(\d+)", url)
        sku = item_m.group(1) if item_m else None
        total = (price or 0) + shipping

        return ProductData(
            url=url,
            platform=Platform.EBAY,
            title=title,
            price=price,
            shipping=shipping,
            total_cost=total if price else None,
            sku=sku,
            seller="eBay Seller",
        )

    @staticmethod
    def _price(soup: BeautifulSoup) -> Optional[float]:
        for sel in (".x-price-primary .ux-textspans", ".notranslate"):
            el = soup.select_one(sel)
            if el:
                m = re.search(r"[\d,]+\.?\d*", el.get_text(strip=True))
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
