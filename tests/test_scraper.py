"""
Unit tests for scraping and parsing utilities.
Run: pytest tests/ -v
"""
import json
from pathlib import Path

import pytest

DEMO = json.loads((Path(__file__).parent / "demo_data.json").read_text())


def test_structured_data_parser_jsonld():
    from backend.scraper.parser import StructuredDataParser

    html = """<html><head><script type="application/ld+json">
    {
      "@type": "Product",
      "name": "Sony WH-1000XM5 Headphones",
      "brand": {"@type": "Brand", "name": "Sony"},
      "model": "WH-1000XM5",
      "gtin13": "027242934580",
      "offers": {
        "@type": "Offer",
        "price": "349.99",
        "priceCurrency": "USD",
        "availability": "InStock"
      },
      "aggregateRating": {
        "ratingValue": "4.7",
        "reviewCount": "12453"
      }
    }
    </script></head></html>"""

    result = StructuredDataParser.extract(html, "https://example.com")

    assert result["title"] == "Sony WH-1000XM5 Headphones"
    assert result["brand"] == "Sony"
    assert result["price"] == 349.99
    assert result["model_number"] == "WH-1000XM5"
    assert result["gtin"] == "027242934580"
    assert result["rating"] == 4.7
    assert result["review_count"] == 12453


def test_platform_detection():
    from backend.scraper.factory import detect_platform

    assert detect_platform("https://www.amazon.com/dp/B0CH7QFGM3") == "amazon"
    assert detect_platform("https://www.amazon.in/dp/B0CH7QFGM3") == "amazon"
    assert detect_platform("https://www.ebay.com/itm/123456789") == "ebay"
    assert detect_platform("https://www.walmart.com/ip/foo/12345") == "walmart"
    assert detect_platform("https://www.bestbuy.com/site/product") == "unknown"


def test_asin_extraction():
    from backend.scraper.amazon import AmazonScraper

    assert AmazonScraper._asin("https://www.amazon.com/dp/B0CH7QFGM3") == "B0CH7QFGM3"
    assert AmazonScraper._asin("https://www.amazon.com/gp/product/B0CH7QFGM3") == "B0CH7QFGM3"
    assert AmazonScraper._asin("https://www.amazon.com/s?k=headphones") is None


def test_query_generation():
    from backend.engine import ComparisonEngine
    from backend.models import Platform, ProductData

    product = ProductData(**DEMO["sony_headphones_amazon"])
    engine = ComparisonEngine()
    queries = engine._queries(product)

    assert len(queries) >= 1
    assert any("Sony" in q for q in queries)
    assert any("WH-1000XM5" in q for q in queries)
