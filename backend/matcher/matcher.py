from __future__ import annotations

from typing import List, Optional, Tuple

from rapidfuzz import fuzz

from backend.config import settings
from backend.models import ComparisonResult, ConfidenceLevel, MatchResult, ProductData


class ProductMatcher:
    """Match a source product against candidate products using multiple signals."""

    def __init__(self) -> None:
        self.t_exact  = settings.SIMILARITY_THRESHOLD_EXACT
        self.t_high   = settings.SIMILARITY_THRESHOLD_HIGH
        self.t_medium = settings.SIMILARITY_THRESHOLD_MEDIUM

    # ------------------------------------------------------------------
    def match(self, source: ProductData, candidates: List[ProductData]) -> List[MatchResult]:
        results = []
        for c in candidates:
            r = self._compare(source, c)
            if r:
                results.append(r)

        results.sort(
            key=lambda r: (
                {"exact": 0, "high": 1, "medium": 2, "low": 3, "unknown": 4}[r.confidence],
                -(r.similarity_score),
                r.match.total_cost or float("inf"),
            )
        )
        return results

    # ------------------------------------------------------------------
    def _compare(self, source: ProductData, candidate: ProductData) -> Optional[MatchResult]:
        exact, reason = self._exact_ids(source, candidate)
        if exact:
            confidence  = ConfidenceLevel.EXACT
            similarity  = 1.0
            match_reason = reason
        else:
            title_sim = fuzz.token_sort_ratio(
                source.title.lower(), candidate.title.lower()
            ) / 100.0

            try:
                emb_sim = self._embed_sim(source, candidate)
            except Exception:
                emb_sim = title_sim

            similarity = 0.4 * title_sim + 0.6 * emb_sim

            if similarity >= self.t_exact:
                confidence   = ConfidenceLevel.EXACT
                match_reason = "Near-identical title & description"
            elif similarity >= self.t_high:
                confidence   = ConfidenceLevel.HIGH
                match_reason = f"High similarity ({similarity:.0%})"
            elif similarity >= self.t_medium:
                confidence   = ConfidenceLevel.MEDIUM
                match_reason = f"Moderate similarity ({similarity:.0%}) — verify before buying"
            else:
                confidence   = ConfidenceLevel.LOW
                match_reason = f"Low similarity ({similarity:.0%}) — may not be same product"

        # Drop only truly irrelevant results (very low similarity AND no price)
        if confidence == ConfidenceLevel.LOW and similarity < 0.15:
            return None

        src_total = source.total_cost or source.price
        cnd_total = candidate.total_cost or candidate.price

        savings_amount:  Optional[float] = None
        savings_percent: Optional[float] = None
        # Only calculate savings if both prices are in the same currency
        if src_total and cnd_total and source.currency == candidate.currency:
            savings_amount  = round(src_total - cnd_total, 2)
            savings_percent = round((savings_amount / src_total) * 100, 2)

        return MatchResult(
            source=source,
            match=candidate,
            confidence=confidence,
            similarity_score=round(similarity, 4),
            match_reason=match_reason,
            savings_amount=savings_amount,
            savings_percent=savings_percent,
        )

    # ------------------------------------------------------------------
    @staticmethod
    def _exact_ids(a: ProductData, b: ProductData) -> Tuple[bool, str]:
        if a.gtin and b.gtin and a.gtin == b.gtin:
            return True, f"Exact GTIN match ({a.gtin})"
        if a.asin and b.asin and a.asin == b.asin:
            return True, f"Exact ASIN match ({a.asin})"
        if a.model_number and b.model_number:
            norm = lambda s: s.upper().replace("-", "").replace(" ", "")
            if norm(a.model_number) == norm(b.model_number):
                return True, f"Exact model number ({a.model_number})"
        return False, ""

    @staticmethod
    def _embed_sim(a: ProductData, b: ProductData) -> float:
        from backend.matcher.embeddings import encode, cosine_sim
        vecs = encode([a.search_text(), b.search_text()])
        return cosine_sim(vecs[0], vecs[1])

    # ------------------------------------------------------------------
    def build_comparison(
        self,
        source: ProductData,
        matches: List[MatchResult],
        elapsed: float = 0.0,
        errors: Optional[List[str]] = None,
    ) -> ComparisonResult:
        # Show ALL results — never silently drop based on confidence alone
        # LOW confidence results are shown but clearly labelled in the UI
        all_matches = sorted(
            matches,
            key=lambda r: (
                {"exact": 0, "high": 1, "medium": 2, "low": 3, "unknown": 4}[r.confidence],
                -(r.similarity_score),
            ),
        )

        exact_matches = [m for m in all_matches if m.confidence == ConfidenceLevel.EXACT]
        cheapest_exact: Optional[MatchResult] = None
        if exact_matches:
            cheapest_exact = min(
                (m for m in exact_matches if m.match.total_cost or m.match.price),
                key=lambda m: m.match.total_cost or m.match.price or float("inf"),
                default=None,
            )

        best_value = self._best_value(source, all_matches)
        if best_value:
            best_value.is_better_value = True

        return ComparisonResult(
            source_product=source,
            matches=all_matches[:15],
            cheapest_exact=cheapest_exact,
            best_value=best_value,
            total_savings=cheapest_exact.savings_amount if cheapest_exact else None,
            search_time_seconds=elapsed,
            errors=errors or [],
        )

    def _best_value(self, source: ProductData, matches: List[MatchResult]) -> Optional[MatchResult]:
        src_total = source.total_cost or source.price or 0
        scored = []
        for m in matches:
            total = m.match.total_cost or m.match.price
            if total is None:
                continue
            # Only score value when same currency
            if source.currency == m.match.currency and src_total > 0:
                price_score = (src_total - total) / src_total
            else:
                price_score = 0
            rating_score = (m.match.rating or 3.0) / 5.0
            conf_bonus = {"exact": 1.0, "high": 0.8, "medium": 0.5, "low": 0.2}.get(
                m.confidence, 0.3
            )
            score = 0.5 * price_score + 0.3 * rating_score + 0.2 * conf_bonus
            scored.append((m, score))

        if not scored:
            return None
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[0][0]
