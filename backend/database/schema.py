from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from backend.config import settings


class Base(DeclarativeBase):
    pass


class CachedProduct(Base):
    __tablename__ = "cached_products"

    url = Column(String, primary_key=True)
    platform = Column(String)
    title = Column(String)
    price = Column(Float, nullable=True)
    currency = Column(String, default="USD")
    shipping = Column(Float, nullable=True)
    total_cost = Column(Float, nullable=True)
    brand = Column(String, nullable=True)
    model_number = Column(String, nullable=True)
    sku = Column(String, nullable=True)
    gtin = Column(String, nullable=True)
    asin = Column(String, nullable=True)
    rating = Column(Float, nullable=True)
    review_count = Column(Integer, nullable=True)
    seller = Column(String, nullable=True)
    raw_data = Column(Text, nullable=True)   # full ProductData JSON
    cached_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)


class SearchCache(Base):
    __tablename__ = "search_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    query = Column(String, index=True)
    platform = Column(String)
    results_json = Column(Text)
    cached_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)


_engine = None
_Session = None


def get_engine():
    global _engine, _Session
    if _engine is None:
        _engine = create_engine(
            settings.DATABASE_URL,
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(_engine)
        _Session = sessionmaker(bind=_engine)
    return _engine


def get_session():
    get_engine()
    return _Session()
