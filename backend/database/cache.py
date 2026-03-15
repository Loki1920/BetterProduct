from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import List, Optional

from backend.config import settings
from backend.database.schema import CachedProduct, SearchCache, get_session
from backend.models import ProductData


class ProductCache:
    def get(self, url: str) -> Optional[ProductData]:
        session = get_session()
        try:
            row = (
                session.query(CachedProduct)
                .filter(
                    CachedProduct.url == url,
                    CachedProduct.expires_at > datetime.utcnow(),
                )
                .first()
            )
            if row and row.raw_data:
                return ProductData.model_validate_json(row.raw_data)
            return None
        finally:
            session.close()

    def set(self, product: ProductData) -> None:
        session = get_session()
        try:
            expires_at = datetime.utcnow() + timedelta(seconds=settings.PRODUCT_CACHE_TTL)
            row = CachedProduct(
                url=product.url,
                platform=product.platform.value,
                title=product.title,
                price=product.price,
                currency=product.currency,
                shipping=product.shipping,
                total_cost=product.total_cost,
                brand=product.brand,
                model_number=product.model_number,
                sku=product.sku,
                gtin=product.gtin,
                asin=product.asin,
                rating=product.rating,
                review_count=product.review_count,
                seller=product.seller,
                raw_data=product.model_dump_json(),
                expires_at=expires_at,
            )
            session.merge(row)
            session.commit()
        except Exception:
            session.rollback()
        finally:
            session.close()


    def clear(self) -> None:
        session = get_session()
        try:
            session.query(CachedProduct).delete()
            session.commit()
        except Exception:
            session.rollback()
        finally:
            session.close()


class SearchResultCache:
    def get(self, query: str, platform: str) -> Optional[List[ProductData]]:
        session = get_session()
        try:
            row = (
                session.query(SearchCache)
                .filter(
                    SearchCache.query == query,
                    SearchCache.platform == platform,
                    SearchCache.expires_at > datetime.utcnow(),
                )
                .order_by(SearchCache.cached_at.desc())
                .first()
            )
            if row:
                data = json.loads(row.results_json)
                return [ProductData.model_validate(d) for d in data]
            return None
        finally:
            session.close()

    def set(self, query: str, platform: str, results: List[ProductData]) -> None:
        session = get_session()
        try:
            expires_at = datetime.utcnow() + timedelta(seconds=settings.SEARCH_CACHE_TTL)
            row = SearchCache(
                query=query,
                platform=platform,
                results_json=json.dumps([r.model_dump(mode="json") for r in results]),
                expires_at=expires_at,
            )
            session.add(row)
            session.commit()
        except Exception:
            session.rollback()
        finally:
            session.close()


    def clear(self) -> None:
        session = get_session()
        try:
            session.query(SearchCache).delete()
            session.commit()
        except Exception:
            session.rollback()
        finally:
            session.close()


product_cache = ProductCache()
search_cache = SearchResultCache()
