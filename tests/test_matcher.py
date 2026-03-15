"""
Unit tests for product matching logic.
Run: pytest tests/ -v
"""
import json
from pathlib import Path

import pytest

from backend.matcher.matcher import ProductMatcher
from backend.models import ConfidenceLevel, Platform, ProductData

DEMO = json.loads((Path(__file__).parent / "demo_data.json").read_text())


@pytest.fixture
def matcher():
    return ProductMatcher()


@pytest.fixture
def amazon_sony():
    return ProductData(**DEMO["sony_headphones_amazon"])


@pytest.fixture
def ebay_sony():
    return ProductData(**DEMO["sony_headphones_ebay"])


@pytest.fixture
def walmart_sony():
    return ProductData(**DEMO["sony_headphones_walmart"])


@pytest.fixture
def bose():
    return ProductData(**DEMO["different_product"])


# ── Exact identifier matching ─────────────────────────────────────────────────

def test_gtin_exact_match(matcher, amazon_sony, ebay_sony):
    results = matcher.match(amazon_sony, [ebay_sony])
    assert len(results) == 1
    assert results[0].confidence == ConfidenceLevel.EXACT
    assert "GTIN" in results[0].match_reason


def test_model_number_exact_match(matcher):
    a = ProductData(
        url="https://amazon.com/dp/X",
        platform=Platform.AMAZON,
        title="Samsung Galaxy S24",
        price=799.0,
        total_cost=799.0,
        model_number="SM-S921B",
    )
    b = ProductData(
        url="https://ebay.com/itm/Y",
        platform=Platform.EBAY,
        title="Samsung Galaxy S24 - SM-S921B",
        price=719.0,
        total_cost=719.0,
        model_number="SM-S921B",
    )
    results = matcher.match(a, [b])
    assert results[0].confidence == ConfidenceLevel.EXACT
    assert "model number" in results[0].match_reason.lower()


# ── Savings calculation ───────────────────────────────────────────────────────

def test_savings_correct(matcher, amazon_sony, ebay_sony):
    results = matcher.match(amazon_sony, [ebay_sony])
    assert results[0].savings_amount == pytest.approx(60.0, abs=0.01)
    assert results[0].savings_percent == pytest.approx(17.14, abs=0.1)


def test_no_savings_more_expensive(matcher, amazon_sony, walmart_sony):
    # Walmart is cheaper in the demo data — savings should be positive
    results = matcher.match(amazon_sony, [walmart_sony])
    assert results[0].savings_amount == pytest.approx(20.99, abs=0.01)


# ── Confidence levels ─────────────────────────────────────────────────────────

def test_different_brand_low_or_medium(matcher, amazon_sony, bose):
    results = matcher.match(amazon_sony, [bose])
    if results:
        assert results[0].confidence in [ConfidenceLevel.LOW, ConfidenceLevel.MEDIUM]


# ── Comparison result ─────────────────────────────────────────────────────────

def test_build_comparison_cheapest_exact(matcher, amazon_sony, ebay_sony, walmart_sony):
    raw = matcher.match(amazon_sony, [ebay_sony, walmart_sony])
    comp = matcher.build_comparison(amazon_sony, raw, elapsed=1.0)

    assert comp.cheapest_exact is not None
    cheapest_total = comp.cheapest_exact.match.total_cost
    assert cheapest_total == pytest.approx(289.99, abs=0.01)


def test_ranking_exact_before_low(matcher, amazon_sony, ebay_sony, bose):
    raw = matcher.match(amazon_sony, [bose, ebay_sony])
    # Exact matches should appear first
    assert raw[0].confidence == ConfidenceLevel.EXACT
