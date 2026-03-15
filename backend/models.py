from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ConfidenceLevel(str, Enum):
    EXACT = "exact"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class Platform(str, Enum):
    AMAZON = "amazon"
    EBAY = "ebay"
    WALMART = "walmart"
    UNKNOWN = "unknown"


class ProductData(BaseModel):
    url: str
    platform: Platform = Platform.UNKNOWN
    title: str
    price: Optional[float] = None
    currency: Optional[str] = "USD"
    shipping: Optional[float] = None
    total_cost: Optional[float] = None
    brand: Optional[str] = None
    model_number: Optional[str] = None
    sku: Optional[str] = None
    gtin: Optional[str] = None        # UPC / EAN / GTIN-13
    asin: Optional[str] = None        # Amazon ASIN
    rating: Optional[float] = None
    review_count: Optional[int] = None
    seller: Optional[str] = None
    availability: Optional[str] = None
    description: Optional[str] = None
    specs: Dict[str, str] = Field(default_factory=dict)
    images: List[str] = Field(default_factory=list)
    categories: List[str] = Field(default_factory=list)
    scraped_at: datetime = Field(default_factory=datetime.utcnow)

    def computed_total(self) -> Optional[float]:
        if self.price is None:
            return None
        return self.price + (self.shipping or 0.0)

    def identifiers(self) -> Dict[str, str]:
        ids: Dict[str, str] = {}
        if self.gtin:
            ids["gtin"] = self.gtin
        if self.asin:
            ids["asin"] = self.asin
        if self.model_number:
            ids["model_number"] = self.model_number
        if self.sku:
            ids["sku"] = self.sku
        return ids

    def search_text(self) -> str:
        parts: List[str] = []
        if self.brand:
            parts.append(self.brand)
        parts.append(self.title)
        if self.model_number:
            parts.append(self.model_number)
        if self.description:
            parts.append(self.description[:200])
        return " ".join(parts)


class MatchResult(BaseModel):
    source: ProductData
    match: ProductData
    confidence: ConfidenceLevel = ConfidenceLevel.UNKNOWN
    similarity_score: float = 0.0
    match_reason: str = ""
    savings_amount: Optional[float] = None
    savings_percent: Optional[float] = None
    explanation: str = ""
    is_better_value: bool = False


class ComparisonResult(BaseModel):
    source_product: ProductData
    matches: List[MatchResult] = Field(default_factory=list)
    cheapest_exact: Optional[MatchResult] = None
    best_value: Optional[MatchResult] = None
    total_savings: Optional[float] = None
    search_time_seconds: float = 0.0
    errors: List[str] = Field(default_factory=list)
    # Debug info — always populated so the UI can show what happened
    debug_queries: List[str] = Field(default_factory=list)
    debug_candidates_found: int = 0
    debug_platforms_searched: List[str] = Field(default_factory=list)
