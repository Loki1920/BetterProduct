"""
UniversalShoppingScraper
------------------------
Searches DuckDuckGo → Bing → Google Shopping in parallel.
Returns merged, deduplicated results from ANY store on the web.
No API key needed. Zero config.
"""
from __future__ import annotations

import asyncio
import logging
from typing import List, Optional
from urllib.parse import urlparse

from backend.models import ProductData

logger = logging.getLogger(__name__)


class UniversalShoppingScraper:
    """
    Tries multiple search engines concurrently and merges results.

    Search order (all run in parallel):
      1. DuckDuckGo Shopping  — primary, no bot risk
      2. Bing Shopping        — good global + India coverage
      3. Google Shopping      — broadest but highest block risk

    Results are deduplicated by URL and ranked by relevance (search engine order).
    """

    async def search(self, query: str, max_results: int = 10) -> List[ProductData]:
        from backend.scraper.duckduckgo_shopping import DuckDuckGoShopping
        from backend.scraper.bing_shopping import BingShoppingScraper
        from backend.scraper.google_shopping import GoogleShoppingScraper

        scrapers = [
            ("DuckDuckGo", DuckDuckGoShopping),
            ("Bing",       BingShoppingScraper),
            ("Google",     GoogleShoppingScraper),
        ]

        tasks = [
            self._safe_search(name, cls, query, max_results)
            for name, cls in scrapers
        ]
        batches = await asyncio.gather(*tasks)

        # Merge and deduplicate — preserve order (DDG first, then Bing, then Google)
        seen_urls: set = set()
        seen_titles: set = set()
        products: List[ProductData] = []

        for batch in batches:
            for p in batch:
                # Deduplicate by URL
                url_key = _norm_url(p.url)
                # Also deduplicate very similar titles from same store
                title_key = f"{p.title[:40].lower()}|{(p.seller or '').lower()}"

                if url_key in seen_urls or title_key in seen_titles:
                    continue
                seen_urls.add(url_key)
                seen_titles.add(title_key)
                products.append(p)

                if len(products) >= max_results * 2:   # fetch extra; caller caps at max
                    break

        return products[:max_results]

    async def _safe_search(
        self, name: str, scraper_cls, query: str, max_results: int
    ) -> List[ProductData]:
        try:
            async with scraper_cls() as s:
                results = await s.search(query, max_results)
            logger.debug("%s returned %d results for '%s'", name, len(results), query)
            return results
        except Exception as exc:
            logger.warning("%s search failed for '%s': %s", name, query, exc)
            return []


def _norm_url(url: str) -> str:
    """Normalise a URL for deduplication (strip tracking params, trailing slash)."""
    try:
        p = urlparse(url)
        return f"{p.netloc}{p.path}".rstrip("/").lower()
    except Exception:
        return url.lower()
