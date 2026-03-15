"""
Structured data extractor — JSON-LD → microdata → OpenGraph fallback.
Always try this before platform-specific DOM scraping.
"""
from __future__ import annotations

from typing import Any, Dict, List

try:
    import extruct
    HAS_EXTRUCT = True
except ImportError:
    HAS_EXTRUCT = False

from bs4 import BeautifulSoup


class StructuredDataParser:
    """Extract product data from page structured data."""

    @staticmethod
    def extract(html: str, url: str = "") -> Dict[str, Any]:
        result: Dict[str, Any] = {}

        if HAS_EXTRUCT:
            try:
                data = extruct.extract(
                    html,
                    base_url=url,
                    uniform=True,
                    syntaxes=["json-ld", "microdata", "opengraph"],
                )
                for item in data.get("json-ld", []):
                    if item.get("@type") in ("Product", "http://schema.org/Product"):
                        result.update(StructuredDataParser._parse_jsonld(item, url))
                        break

                if not result and data.get("microdata"):
                    for item in data["microdata"]:
                        if "Product" in str(item.get("type", "")):
                            result.update(StructuredDataParser._parse_microdata(item))
                            break

                og_list = data.get("opengraph", [])
                og = og_list[0] if og_list else {}
                if not result.get("title") and og.get("og:title"):
                    result["title"] = og["og:title"]
                if not result.get("images") and og.get("og:image"):
                    result["images"] = [og["og:image"]]
                if not result.get("description") and og.get("og:description"):
                    result["description"] = og["og:description"]
            except Exception:
                pass
        else:
            # Manual JSON-LD fallback via BeautifulSoup
            import json
            soup = BeautifulSoup(html, "lxml")
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    obj = json.loads(script.string or "")
                    if isinstance(obj, list):
                        obj = next((x for x in obj if x.get("@type") == "Product"), {})
                    if obj.get("@type") == "Product":
                        result.update(StructuredDataParser._parse_jsonld(obj, url))
                        break
                except Exception:
                    continue

        return result

    # ------------------------------------------------------------------
    _DOMAIN_CURRENCY: Dict[str, str] = {
        "amazon.in":     "INR",
        "flipkart.com":  "INR",
        "amazon.co.uk":  "GBP",
        "amazon.de":     "EUR",
        "amazon.fr":     "EUR",
        "amazon.it":     "EUR",
        "amazon.es":     "EUR",
        "amazon.nl":     "EUR",
        "amazon.ca":     "CAD",
        "amazon.com.au": "AUD",
        "amazon.co.jp":  "JPY",
    }

    @staticmethod
    def _infer_currency(url: str) -> str:
        from urllib.parse import urlparse
        try:
            host = urlparse(url).hostname or ""
        except Exception:
            host = ""
        for domain, currency in StructuredDataParser._DOMAIN_CURRENCY.items():
            if host.endswith(domain):
                return currency
        return "USD"

    @staticmethod
    def _parse_jsonld(item: Dict, base_url: str = "") -> Dict[str, Any]:
        r: Dict[str, Any] = {}
        r["title"] = item.get("name", "")
        r["description"] = item.get("description", "")
        r["brand"] = StructuredDataParser._name(item.get("brand"))
        r["model_number"] = item.get("model") or item.get("mpn") or ""
        r["gtin"] = (
            item.get("gtin13")
            or item.get("gtin12")
            or item.get("gtin8")
            or item.get("gtin")
            or ""
        )
        r["sku"] = item.get("sku", "")

        images: Any = item.get("image", [])
        if isinstance(images, str):
            images = [images]
        elif isinstance(images, dict):
            images = [images.get("url", "")]
        r["images"] = [i for i in images if i]

        offers: Any = item.get("offers") or item.get("offer") or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        if offers:
            try:
                r["price"] = float(str(offers.get("price", offers.get("lowPrice", "0"))).replace(",", ""))
            except (ValueError, TypeError):
                pass
            r["currency"] = offers.get("priceCurrency") or StructuredDataParser._infer_currency(base_url)
            r["availability"] = offers.get("availability", "").replace("http://schema.org/", "")
            r["seller"] = StructuredDataParser._name(offers.get("seller"))

        agg: Any = item.get("aggregateRating") or {}
        if agg:
            try:
                r["rating"] = float(agg.get("ratingValue", 0))
                r["review_count"] = int(agg.get("reviewCount") or agg.get("ratingCount") or 0)
            except (ValueError, TypeError):
                pass

        specs: Dict[str, str] = {}
        for prop in item.get("additionalProperty", []):
            if isinstance(prop, dict):
                k, v = prop.get("name", ""), prop.get("value", "")
                if k and v:
                    specs[k] = str(v)
        r["specs"] = specs

        return {k: v for k, v in r.items() if v or v == 0}

    @staticmethod
    def _parse_microdata(item: Dict) -> Dict[str, Any]:
        props = item.get("properties", {})

        def first(key: str, fallback: str = "") -> str:
            val = props.get(key, [fallback])
            return val[0] if val else fallback

        r: Dict[str, Any] = {
            "title": first("name"),
            "description": first("description"),
            "model_number": first("model") or first("mpn"),
            "sku": first("sku"),
            "gtin": first("gtin13") or first("gtin"),
        }
        brand = props.get("brand", [{}])
        if brand and isinstance(brand[0], dict):
            r["brand"] = brand[0].get("properties", {}).get("name", [""])[0]
        return {k: v for k, v in r.items() if v}

    @staticmethod
    def _name(obj: Any) -> str:
        if isinstance(obj, str):
            return obj
        if isinstance(obj, dict):
            return obj.get("name", "")
        return ""
