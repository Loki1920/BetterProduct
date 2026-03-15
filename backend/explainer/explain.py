from __future__ import annotations

from typing import Optional

from backend.models import ConfidenceLevel, MatchResult, ProductData


class Explainer:
    """Generate human-readable explanations for match results."""

    def explain_match(self, result: MatchResult) -> str:
        parts: list[str] = []
        c = result.confidence
        m = result.match
        s = result.source

        # --- Why it was matched ---
        if c == ConfidenceLevel.EXACT:
            parts.append(f"**Exact match** — {result.match_reason}.")
        elif c == ConfidenceLevel.HIGH:
            parts.append(f"**Very likely the same product** — {result.match_reason}.")
        elif c == ConfidenceLevel.MEDIUM:
            parts.append(f"**Possibly the same product** — {result.match_reason}. Verify before purchasing.")
        else:
            parts.append(f"**Similar product** — {result.match_reason}. Inspect listing carefully.")

        # --- Price comparison ---
        src_total = s.total_cost or s.price
        cnd_total = m.total_cost or m.price
        if src_total and cnd_total:
            if result.savings_amount and result.savings_amount > 0:
                parts.append(
                    f"Saves **${result.savings_amount:.2f}** "
                    f"({result.savings_percent:.1f}% cheaper) vs. source "
                    f"(${src_total:.2f} → ${cnd_total:.2f} incl. shipping)."
                )
            elif result.savings_amount and result.savings_amount < 0:
                extra = abs(result.savings_amount)
                parts.append(
                    f"Costs **${extra:.2f} more** ({abs(result.savings_percent or 0):.1f}% pricier) "
                    f"than source."
                )
            else:
                parts.append("Same price as source.")

        # --- Rating comparison ---
        if m.rating and s.rating:
            diff = m.rating - s.rating
            if diff > 0.2:
                parts.append(f"Better rated: {m.rating:.1f}★ vs {s.rating:.1f}★.")
            elif diff < -0.2:
                parts.append(f"Lower rated: {m.rating:.1f}★ vs {s.rating:.1f}★.")
        elif m.rating:
            rc = f" ({m.review_count:,} reviews)" if m.review_count else ""
            parts.append(f"Rated {m.rating:.1f}★{rc}.")

        # --- Shipping ---
        if m.shipping == 0:
            parts.append("Free shipping included.")
        elif m.shipping:
            parts.append(f"Shipping: ${m.shipping:.2f}.")

        # --- Best value flag ---
        if result.is_better_value:
            parts.append("✓ **Recommended as best overall value.**")

        return " ".join(parts)

    def explain_source(self, product: ProductData) -> str:
        parts = []
        if product.brand:
            parts.append(f"**Brand:** {product.brand}")
        if product.model_number:
            parts.append(f"**Model:** {product.model_number}")
        if product.price:
            parts.append(f"**Price:** ${product.price:.2f}")
        if product.shipping is not None:
            parts.append("**Shipping:** Free" if product.shipping == 0 else f"**Shipping:** ${product.shipping:.2f}")
        if product.rating:
            rc = f" ({product.review_count:,})" if product.review_count else ""
            parts.append(f"**Rating:** {product.rating:.1f}★{rc}")
        return " | ".join(parts)

    async def explain_with_llm(self, result: MatchResult) -> Optional[str]:
        """Richer explanation via local Ollama LLM — optional."""
        from backend.config import settings
        if not settings.OLLAMA_BASE_URL:
            return None
        try:
            import httpx
            src_t = result.source.total_cost or result.source.price or 0
            cnd_t = result.match.total_cost or result.match.price or 0
            prompt = (
                "You are a helpful shopping assistant. In 2-3 concise sentences explain "
                "why this product match is shown to the shopper.\n\n"
                f"Source: {result.source.title} at ${src_t:.2f}\n"
                f"Match: {result.match.title} at ${cnd_t:.2f} on {result.match.platform.value}\n"
                f"Confidence: {result.confidence.value}\nReason: {result.match_reason}"
            )
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{settings.OLLAMA_BASE_URL}/api/generate",
                    json={"model": settings.OLLAMA_MODEL, "prompt": prompt, "stream": False},
                    timeout=30.0,
                )
            return resp.json().get("response", "").strip() or None
        except Exception:
            return None
