"""
ComparisonEngine
----------------
Scrapes the source product, then uses UniversalShoppingScraper to find
the same product on ANY store across the web (DuckDuckGo + Bing + Google Shopping).
"""
from __future__ import annotations

import asyncio
import re
import time
from typing import List, Optional

from backend.database.cache import product_cache, search_cache
from backend.explainer.explain import Explainer
from backend.matcher.matcher import ProductMatcher
from backend.models import ComparisonResult, ProductData
from backend.scraper.factory import detect_platform, get_scraper
from backend.scraper.universal_search import UniversalShoppingScraper
from backend.config import settings


class ComparisonEngine:
    def __init__(self) -> None:
        self.matcher   = ProductMatcher()
        self.explainer = Explainer()
        self.universal = UniversalShoppingScraper()

    # ------------------------------------------------------------------
    async def compare(self, url: str) -> ComparisonResult:
        t0     = time.time()
        errors: List[str] = []

        # 1. Scrape the source product
        source = await self._scrape_source(url, errors)
        if source is None:
            from backend.models import Platform
            dummy = ProductData(url=url, title="Failed to scrape", platform=Platform.UNKNOWN)
            return ComparisonResult(source_product=dummy, errors=errors)

        # 2. Build search queries from extracted product data
        queries = self._queries(source)

        # 3. Universal search — DuckDuckGo + Bing + Google Shopping in parallel
        candidates, searched_engines = await self._search_universal(queries, url, errors)

        # 4. Match candidates against source
        raw_matches = self.matcher.match(source, candidates)

        # 5. Generate plain-English explanations
        for r in raw_matches:
            r.explanation = self.explainer.explain_match(r)

        # 6. Build final result
        elapsed = time.time() - t0
        result  = self.matcher.build_comparison(source, raw_matches, elapsed, errors)

        # Attach debug info
        result.debug_queries           = queries
        result.debug_candidates_found  = len(candidates)
        result.debug_platforms_searched = searched_engines

        return result

    # ------------------------------------------------------------------
    async def _scrape_source(self, url: str, errors: List[str]) -> Optional[ProductData]:
        cached = product_cache.get(url)
        if cached:
            return cached

        platform = detect_platform(url)
        scraper  = get_scraper(platform)
        try:
            async with scraper as s:
                product = await s.scrape_product(url)
            product_cache.set(product)
            return product
        except Exception as exc:
            errors.append(f"Source scrape failed: {exc}")
            return None

    # ------------------------------------------------------------------
    def _queries(self, p: ProductData) -> List[str]:
        """Build search queries, best → broadest."""
        queries: List[str] = []

        clean_model = self._clean_model(p.model_number) if p.model_number else None
        clean_title = self._clean_title(p.title)

        if p.brand and clean_model:
            queries.append(f"{p.brand} {clean_model}")
        if p.brand and clean_title:
            queries.append(f"{p.brand} {clean_title[:60]}")
        if clean_title:
            queries.append(clean_title[:80])
        # Broad fallback: brand + first 3 meaningful words
        if p.brand:
            words = [w for w in clean_title.split() if len(w) > 2][:3]
            if words:
                queries.append(f"{p.brand} {' '.join(words)}")
        if p.gtin:
            queries.append(p.gtin)

        # Deduplicate preserving order
        seen: set = set()
        deduped: List[str] = []
        for q in queries:
            q = q.strip()
            if q and q not in seen:
                seen.add(q)
                deduped.append(q)
        return deduped[:4]

    @staticmethod
    def _clean_model(model: str) -> str:
        model = re.sub(r"(?<=[A-Z0-9])ID(?=-)", "", model)
        model = re.sub(r"/[A-Z]{1,2}$", "", model)
        return model.strip()

    @staticmethod
    def _clean_title(title: str) -> str:
        title = re.sub(r"\b(UK|US|EU|IN|Size[-\s]?)\s*\d+(\.\d+)?\b", "", title, flags=re.IGNORECASE)
        colours = (r"\b(Black|White|Navy|Blue|Red|Green|Grey|Gray|Brown|Beige|"
                   r"Silver|Gold|Pink|Purple|Orange|Yellow|Charcoal|Khaki|Tan)\b")
        title = re.sub(colours, "", title, flags=re.IGNORECASE)
        title = re.sub(r"\b[A-Z0-9]{3,}-[A-Z0-9]+\b", "", title)
        title = re.sub(r"\s{2,}", " ", title).strip()
        return title

    # ------------------------------------------------------------------
    async def _search_universal(
        self, queries: List[str], source_url: str, errors: List[str]
    ) -> tuple[List[ProductData], List[str]]:
        """
        Run universal search for all queries concurrently.
        Returns (candidates, list_of_engines_used).
        """
        source_domain = self._source_domain(source_url)

        tasks = [
            self._search_one_query(query, source_domain, errors)
            for query in queries[:3]      # top 3 queries in parallel
        ]
        batches = await asyncio.gather(*tasks)

        seen_urls: set = set()
        candidates: List[ProductData] = []
        for batch in batches:
            for p in batch:
                if p.url and p.url not in seen_urls:
                    seen_urls.add(p.url)
                    candidates.append(p)

        engines = ["DuckDuckGo Shopping", "Bing Shopping", "Google Shopping"]
        return candidates, engines

    async def _search_one_query(
        self, query: str, source_domain: str, errors: List[str]
    ) -> List[ProductData]:
        # Check cache first
        cached = search_cache.get(query, "universal")
        if cached:
            return cached

        try:
            results = await self.universal.search(query, max_results=settings.MAX_SEARCH_RESULTS * 2)
            # Filter out results from the same site as the source
            filtered = [
                p for p in results
                if source_domain not in (p.url or "").lower()
            ]
            search_cache.set(query, "universal", filtered)
            return filtered
        except Exception as exc:
            errors.append(f"Universal search failed for '{query}': {exc}")
            return []

    @staticmethod
    def _source_domain(url: str) -> str:
        try:
            from urllib.parse import urlparse
            return urlparse(url).netloc.replace("www.", "").lower()
        except Exception:
            return ""


# Singleton
comparison_engine = ComparisonEngine()
