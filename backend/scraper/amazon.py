from __future__ import annotations

import re
from typing import List, Optional
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup

from backend.models import Platform, ProductData
from backend.scraper.base import BaseScraper
from backend.scraper.parser import StructuredDataParser


class AmazonScraper(BaseScraper):
    PLATFORM_NAME = "amazon"
    BASE_URL = "https://www.amazon.com"

    @staticmethod
    def _base_url_from(url: str) -> str:
        """Return the correct Amazon base URL from the product URL domain."""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"

    @staticmethod
    def _currency_from(url: str) -> str:
        domain = url.lower()
        if "amazon.in" in domain:
            return "INR"
        if "amazon.co.uk" in domain or "amazon.de" in domain:
            return "EUR" if "amazon.de" in domain else "GBP"
        if "amazon.ca" in domain:
            return "CAD"
        if "amazon.com.au" in domain:
            return "AUD"
        return "USD"

    # ------------------------------------------------------------------
    async def scrape_product(self, url: str) -> ProductData:
        page, html = await self.get_page(url, wait_selector="#productTitle")
        soup = BeautifulSoup(html, "lxml")
        sd = StructuredDataParser.extract(html, url)

        title = sd.get("title") or self._text(soup, "#productTitle")
        price = sd.get("price") or self._price(soup)
        brand = sd.get("brand") or self._text(soup, "#bylineInfo")
        if brand:
            brand = re.sub(r"^(Visit the |Brand: )", "", brand).strip()

        rating: Optional[float] = sd.get("rating")
        if not rating:
            el = soup.select_one("#acrPopover")
            if el:
                try:
                    rating = float(el["title"].split()[0])
                except Exception:
                    pass

        review_count: Optional[int] = sd.get("review_count")
        if not review_count:
            el = soup.select_one("#acrCustomerReviewText")
            if el:
                try:
                    review_count = int(re.sub(r"[^\d]", "", el.text))
                except Exception:
                    pass

        specs: dict = sd.get("specs", {})
        for row in soup.select(
            "#productDetails_techSpec_section_1 tr, "
            "#productDetails_detailBullets_sections1 tr, "
            ".prodDetTable tr"
        ):
            cells = row.select("th, td")
            if len(cells) >= 2:
                k = cells[0].get_text(strip=True).rstrip(":")
                v = cells[1].get_text(strip=True)
                if k and v:
                    specs[k] = v

        description = sd.get("description", "")
        if not description:
            bullets = soup.select("#feature-bullets li span:not(.a-list-item)")
            description = " ".join(b.get_text(strip=True) for b in bullets[:3])

        model = sd.get("model_number") or specs.get(
            "Item model number", specs.get("Model Number", "")
        )

        images = sd.get("images", [])
        if not images:
            img = soup.select_one("#landingImage, #imgBlkFront")
            if img:
                src = img.get("data-old-hires") or img.get("src", "")
                if src:
                    images = [src]

        asin = self._asin(url)
        shipping = 0.0
        total = (price + shipping) if price is not None else None
        currency = sd.get("currency") or self._currency_from(url)

        await page.close()
        return ProductData(
            url=url,
            platform=Platform.AMAZON,
            title=title or "Unknown",
            price=price,
            currency=currency,
            shipping=shipping,
            total_cost=total,
            brand=brand or None,
            model_number=model or None,
            sku=sd.get("sku") or None,
            gtin=sd.get("gtin") or None,
            asin=asin,
            rating=rating,
            review_count=review_count,
            seller="Amazon",
            availability=sd.get("availability"),
            description=description,
            specs=specs,
            images=images,
        )

    # ------------------------------------------------------------------
    async def search(self, query: str, max_results: int = 5) -> List[ProductData]:
        url = f"{self.BASE_URL}/s?k={quote_plus(query)}"
        page, html = await self.get_page(url)
        soup = BeautifulSoup(html, "lxml")

        results: List[ProductData] = []
        for item in soup.select("[data-component-type='s-search-result']"):
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
    def _parse_result(self, item) -> Optional[ProductData]:
        title_el = item.select_one("h2 a span")
        if not title_el:
            return None
        title = title_el.get_text(strip=True)

        link = item.select_one("h2 a")
        url = urljoin(self.BASE_URL, link["href"]) if link else ""

        price: Optional[float] = None
        whole = item.select_one(".a-price-whole")
        frac = item.select_one(".a-price-fraction")
        if whole:
            try:
                price = float(
                    re.sub(r"[^\d]", "", whole.text)
                    + "."
                    + (re.sub(r"[^\d]", "", frac.text) if frac else "00")
                )
            except Exception:
                pass

        rating: Optional[float] = None
        r_el = item.select_one(".a-icon-alt")
        if r_el:
            try:
                rating = float(r_el.text.split()[0])
            except Exception:
                pass

        asin = item.get("data-asin") or None
        return ProductData(
            url=url,
            platform=Platform.AMAZON,
            title=title,
            price=price,
            shipping=0.0,
            total_cost=price,
            asin=asin,
            rating=rating,
            seller="Amazon",
        )

    # ------------------------------------------------------------------
    @staticmethod
    def _asin(url: str) -> Optional[str]:
        for pattern in (r"/dp/([A-Z0-9]{10})", r"/gp/product/([A-Z0-9]{10})"):
            m = re.search(pattern, url)
            if m:
                return m.group(1)
        return None

    @staticmethod
    def _price(soup: BeautifulSoup) -> Optional[float]:
        for sel in (
            ".a-price .a-offscreen",
            "#priceblock_ourprice",
            "#priceblock_dealprice",
            "#corePrice_feature_div .a-offscreen",
        ):
            el = soup.select_one(sel)
            if el:
                try:
                    return float(re.sub(r"[^\d.]", "", el.get_text(strip=True)))
                except Exception:
                    continue
        return None

    @staticmethod
    def _text(soup: BeautifulSoup, selector: str) -> str:
        el = soup.select_one(selector)
        return el.get_text(strip=True) if el else ""
