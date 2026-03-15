from __future__ import annotations

from typing import Dict, Type
from urllib.parse import urlparse

from backend.scraper.base import BaseScraper

# Maps domain → internal platform key
# amazon.in is intentionally SEPARATE from amazon.com so that
# when a user pastes an amazon.in URL, amazon.com is still searched.
PLATFORM_DOMAINS: Dict[str, str] = {
    "amazon.com": "amazon",
    "amazon.co.uk": "amazon",
    "amazon.ca": "amazon",
    "amazon.de": "amazon",
    "amazon.com.au": "amazon",
    "amazon.in": "amazon_in",      # Indian Amazon — separate key
    "ebay.com": "ebay",
    "ebay.co.uk": "ebay",
    "ebay.com.au": "ebay",
    "walmart.com": "walmart",
    "flipkart.com": "flipkart",
}

# Which scraper class handles each platform key
def _scraper_map() -> Dict[str, Type[BaseScraper]]:
    from backend.scraper.amazon import AmazonScraper
    from backend.scraper.ebay import EbayScraper
    from backend.scraper.walmart import WalmartScraper
    from backend.scraper.flipkart import FlipkartScraper

    return {
        "amazon":    AmazonScraper,
        "amazon_in": AmazonScraper,   # same scraper, different domain
        "ebay":      EbayScraper,
        "walmart":   WalmartScraper,
        "flipkart":  FlipkartScraper,
    }


# Platforms to search when source is a global (non-India) site
GLOBAL_SEARCH_PLATFORMS = ["amazon", "ebay", "walmart"]

# Platforms to search when source is an Indian site
INDIA_SEARCH_PLATFORMS  = ["amazon_in", "flipkart", "ebay"]

INDIA_PLATFORMS = {"amazon_in", "flipkart"}


def detect_platform(url: str) -> str:
    domain = urlparse(url.lower()).netloc.replace("www.", "")
    for known, platform in PLATFORM_DOMAINS.items():
        if domain == known or domain.endswith(f".{known}"):
            return platform
    return "unknown"


def is_india_platform(platform: str) -> bool:
    return platform in INDIA_PLATFORMS


def get_search_platform_list(source_platform: str) -> list[str]:
    """Return the list of platforms to search, excluding the source."""
    if is_india_platform(source_platform):
        return [p for p in INDIA_SEARCH_PLATFORMS if p != source_platform]
    return [p for p in GLOBAL_SEARCH_PLATFORMS if p != source_platform]


def get_scraper(platform: str, **kwargs) -> BaseScraper:
    scraper_map = _scraper_map()
    cls = scraper_map.get(platform)
    if cls is None:
        from backend.scraper.generic import GenericScraper
        return GenericScraper(**kwargs)
    return cls(**kwargs)
