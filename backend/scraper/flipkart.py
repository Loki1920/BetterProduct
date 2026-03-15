from __future__ import annotations

import re
from typing import List, Optional
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup

from backend.models import Platform, ProductData
from backend.scraper.base import BaseScraper
from backend.scraper.parser import StructuredDataParser


class FlipkartScraper(BaseScraper):
    PLATFORM_NAME = "flipkart"
    BASE_URL = "https://www.flipkart.com"

    async def scrape_product(self, url: str) -> ProductData:
        page, html = await self.get_page(url, wait_selector="._30jeq3, .B_NuCI")
        html = await page.content()
        soup = BeautifulSoup(html, "lxml")
        sd = StructuredDataParser.extract(html, url)

        title = (
            sd.get("title")
            or self._text(soup, ".B_NuCI")
            or self._text(soup, "h1.yhB1nd")
            or self._text(soup, "h1")
        )

        price = sd.get("price") or self._price(soup)

        # Flipkart shipping is usually free above ₹500
        shipping = 0.0
        ship_el = soup.select_one("._3XINqE, .3qQ9m7")
        if ship_el:
            ship_txt = ship_el.get_text(strip=True).lower()
            if "free" not in ship_txt:
                m = re.search(r"[\d]+", ship_txt)
                if m:
                    try:
                        shipping = float(m.group())
                    except Exception:
                        pass

        # Rating
        rating: Optional[float] = sd.get("rating")
        if not rating:
            r_el = soup.select_one("._3LWZlK")
            if r_el:
                try:
                    rating = float(r_el.get_text(strip=True))
                except Exception:
                    pass

        review_count: Optional[int] = sd.get("review_count")
        if not review_count:
            rc_el = soup.select_one("span._2_R_DZ")
            if rc_el:
                m = re.search(r"[\d,]+", rc_el.get_text(strip=True))
                if m:
                    try:
                        review_count = int(m.group().replace(",", ""))
                    except Exception:
                        pass

        # Specs table
        specs: dict = {}
        for row in soup.select("._14cfVK, ._3_6Uyw .RmoJze"):
            cols = row.select("._1hKmbr, li")
            if len(cols) >= 2:
                specs[cols[0].get_text(strip=True)] = cols[1].get_text(strip=True)
        # Also try table rows
        for row in soup.select("tr"):
            cells = row.select("td")
            if len(cells) >= 2:
                specs[cells[0].get_text(strip=True)] = cells[1].get_text(strip=True)

        brand = sd.get("brand") or specs.get("Brand", "") or specs.get("Manufacturer", "")
        model = sd.get("model_number") or specs.get("Model Number", "") or specs.get("Model Name", "")

        # Flipkart item ID from URL
        pid_m = re.search(r"pid=([A-Z0-9]+)", url)
        sku = pid_m.group(1) if pid_m else None

        images = sd.get("images", [])
        if not images:
            img = soup.select_one("._396cs4, ._2r_T1I img")
            if img:
                src = img.get("src", "")
                if src:
                    images = [src]

        total = (price or 0) + shipping
        await page.close()

        return ProductData(
            url=url,
            platform=Platform.UNKNOWN,   # use UNKNOWN since Platform enum has no FLIPKART
            title=title or "Unknown",
            price=price,
            currency="INR",
            shipping=shipping,
            total_cost=total if price else None,
            brand=brand or None,
            model_number=model or None,
            sku=sku,
            rating=rating,
            review_count=review_count,
            seller="Flipkart",
            specs=specs,
            images=images,
        )

    async def search(self, query: str, max_results: int = 5) -> List[ProductData]:
        url = f"{self.BASE_URL}/search?q={quote_plus(query)}&sort=relevance"
        page, html = await self.get_page(url)
        try:
            await page.wait_for_selector("._1AtVbE, ._13oc-S", timeout=6_000)
            html = await page.content()
        except Exception:
            pass
        soup = BeautifulSoup(html, "lxml")

        results: List[ProductData] = []
        # Flipkart search result cards
        for item in soup.select("._1AtVbE div[data-id], ._13oc-S"):
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
        title_el = item.select_one("._4rR01T, .IRpwTa, .s1Q9rs, a.IRpwTa")
        if not title_el:
            return None
        title = title_el.get_text(strip=True)
        if not title:
            return None

        link = item.select_one("a._1fQZEK, a.IRpwTa, a._2rpwqI, a")
        url = urljoin(self.BASE_URL, link["href"]) if link and link.get("href") else ""

        price: Optional[float] = None
        price_el = item.select_one("._30jeq3, ._1_WHN1")
        if price_el:
            m = re.search(r"[\d,]+", price_el.get_text(strip=True))
            if m:
                try:
                    price = float(m.group().replace(",", ""))
                except Exception:
                    pass

        rating: Optional[float] = None
        r_el = item.select_one("._3LWZlK")
        if r_el:
            try:
                rating = float(r_el.get_text(strip=True))
            except Exception:
                pass

        return ProductData(
            url=url,
            platform=Platform.UNKNOWN,
            title=title,
            price=price,
            currency="INR",
            shipping=0.0,
            total_cost=price,
            rating=rating,
            seller="Flipkart",
        )

    @staticmethod
    def _price(soup: BeautifulSoup) -> Optional[float]:
        for sel in ("._30jeq3", "._16Jk6d", "[class*='price']"):
            el = soup.select_one(sel)
            if el:
                m = re.search(r"[\d,]+", el.get_text(strip=True))
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
