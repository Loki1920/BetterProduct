"""
BetterProduct — Streamlit frontend
Run: streamlit run app.py
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import sys
import os
from typing import Optional

import streamlit as st

# ── Page config (must be first Streamlit call) ───────────────────────────────
st.set_page_config(
    page_title="BetterProduct — Price Comparison",
    page_icon="🛍️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown(
    """
<style>
.main-header { text-align: center; padding: 1.5rem 0 0.5rem; }
.tag {
    display: inline-block; padding: 2px 10px; border-radius: 12px;
    font-size: 0.78rem; font-weight: 700; margin-right: 4px;
}
.tag-exact  { background:#d4edda; color:#155724; }
.tag-high   { background:#cce5ff; color:#004085; }
.tag-medium { background:#fff3cd; color:#856404; }
.tag-low    { background:#f8d7da; color:#721c24; }
.save-pos   { color:#28a745; font-weight:700; }
.save-neg   { color:#dc3545; }
.divider    { border-top: 1px solid #e9ecef; margin: 0.6rem 0; }
</style>
""",
    unsafe_allow_html=True,
)


# ── Helpers ───────────────────────────────────────────────────────────────────
def _run_async(coro):
    """Execute an async coroutine safely from Streamlit's sync context.

    On Windows the default event loop created inside a worker thread is
    SelectorEventLoop, which does NOT support subprocesses (needed by
    Playwright).  We must switch to ProactorEventLoop explicitly.
    """
    import sys

    def _worker():
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_worker).result(timeout=180)


CURRENCY_SYMBOLS = {
    "INR": "₹", "USD": "$", "GBP": "£", "EUR": "€",
    "CAD": "CA$", "AUD": "A$",
}

def _sym(currency: str) -> str:
    return CURRENCY_SYMBOLS.get((currency or "USD").upper(), "$")

def _fmt(amount: Optional[float], currency: str = "USD") -> str:
    if amount is None:
        return "N/A"
    return f"{_sym(currency)}{amount:,.2f}"


def _badge(confidence: str) -> str:
    labels = {
        "exact":   ("✓ Exact Match",        "tag-exact"),
        "high":    ("◉ High Confidence",    "tag-high"),
        "medium":  ("◎ Possibly Same",      "tag-medium"),
        "low":     ("○ Similar Product",    "tag-low"),
    }
    label, css = labels.get(confidence, ("? Unknown", "tag-low"))
    return f'<span class="tag {css}">{label}</span>'


def _platform_icon(platform: str, seller: str = "") -> str:
    """Show a store icon. Prefer seller name (from universal search) over platform key."""
    icons = {
        "amazon":   "🟠", "amazon_in": "🟠",
        "ebay":     "🔴",
        "walmart":  "🔵",
        "flipkart": "🟡",
        "unknown":  "🌐",
    }
    # If we have a real seller name use it; otherwise fall back to platform key
    display = seller if seller and seller not in ("Unknown Store", "Online Store", "") else platform.replace("_", " ").title()
    icon = icons.get(platform, "🌐")
    return f"{icon} {display}"


# ── UI Sections ───────────────────────────────────────────────────────────────
def render_source(product) -> None:
    col_img, col_info = st.columns([1, 3])
    with col_img:
        if product.images:
            st.image(product.images[0], width="stretch")
        else:
            st.markdown("📦 *No image*")
    with col_info:
        st.markdown(f"### {product.title}")
        c1, c2, c3, c4 = st.columns(4)
        cur = product.currency or "USD"
        c1.metric("Price", _fmt(product.price, cur))
        c2.metric(
            "Shipping",
            "Free" if product.shipping == 0 else (_fmt(product.shipping, cur) if product.shipping else "?"),
        )
        total = product.total_cost or product.price
        c3.metric("Total", _fmt(total, cur))
        c4.metric("Rating", f"{product.rating:.1f} ★" if product.rating else "N/A")

        meta = []
        if product.brand:
            meta.append(f"**Brand:** {product.brand}")
        if product.model_number:
            meta.append(f"**Model:** {product.model_number}")
        if product.seller:
            meta.append(f"**Seller:** {product.seller}")
        if product.asin:
            meta.append(f"**ASIN:** {product.asin}")
        if meta:
            st.markdown("  |  ".join(meta))

        if product.specs:
            with st.expander("📋 Technical Specs"):
                items = list(product.specs.items())[:16]
                half = max(len(items) // 2, 1)
                sc1, sc2 = st.columns(2)
                for k, v in items[:half]:
                    sc1.markdown(f"**{k}:** {v}")
                for k, v in items[half:]:
                    sc2.markdown(f"**{k}:** {v}")

        st.markdown(f"[🔗 View original listing]({product.url})")


def render_match(result, rank: int) -> None:
    m = result.match
    total = m.total_cost or m.price

    h1, h2, h3, h4, h5 = st.columns([0.4, 3, 1.3, 1.3, 1])

    with h1:
        st.markdown(f"**#{rank}**")
    with h2:
        title_short = m.title[:90] + ("…" if len(m.title) > 90 else "")
        st.markdown(f"**{title_short}**")
        platform_val = m.platform if isinstance(m.platform, str) else m.platform.value
        platform_html = _platform_icon(platform_val, m.seller or "")
        badge_html = _badge(result.confidence if isinstance(result.confidence, str) else result.confidence.value)
        st.markdown(f"{platform_html} &nbsp; {badge_html}", unsafe_allow_html=True)
    with h3:
        cur = m.currency or "USD"
        st.markdown(f"**{_fmt(total, cur)}**" if total else "**N/A**")
        if m.shipping == 0:
            st.caption("Free shipping")
        elif m.shipping:
            st.caption(f"+{_fmt(m.shipping, cur)} ship")
    with h4:
        if result.savings_amount is not None:
            src_sym = _sym(m.currency or "USD")
            if result.savings_amount > 0:
                st.markdown(
                    f'<span class="save-pos">↓ Save {src_sym}{result.savings_amount:.2f} ({result.savings_percent:.1f}%)</span>',
                    unsafe_allow_html=True,
                )
            elif result.savings_amount < 0:
                st.markdown(
                    f'<span class="save-neg">↑ {src_sym}{abs(result.savings_amount):.2f} more</span>',
                    unsafe_allow_html=True,
                )
            else:
                st.caption("Same price")
    with h5:
        if m.rating:
            st.markdown(f"⭐ {m.rating:.1f}")
            if m.review_count:
                st.caption(f"{m.review_count:,}")

    if result.explanation:
        st.caption(result.explanation)
    if m.url:
        platform_name = m.platform if isinstance(m.platform, str) else m.platform.value
        st.markdown(f"[View on {platform_name.title()} →]({m.url})")
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)


def render_results_list(matches) -> None:
    if not matches:
        st.info("No results in this category.")
        return
    for i, r in enumerate(matches, 1):
        render_match(r, i)


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    st.markdown(
        '<div class="main-header"><h1>🛍️ BetterProduct</h1>'
        "<p>Paste any Amazon, eBay, or Walmart URL — we'll find cheaper alternatives instantly.</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    col_input, col_btn = st.columns([5, 1])
    with col_input:
        url = st.text_input(
            "url",
            placeholder="https://www.amazon.com/dp/...",
            label_visibility="collapsed",
        )
    with col_btn:
        go = st.button("🔍 Compare", type="primary", use_container_width=True)

    st.caption(
        "Supported: amazon.com · ebay.com · walmart.com  |  "
        "Results are scraped live — prices may change."
    )

    # ── Sidebar ────────────────────────────────────────────────────────────────
    with st.sidebar:
        st.header("⚙️ Settings")
        st.markdown(
            "**BetterProduct** searches Amazon, eBay, and Walmart for the same "
            "product and ranks alternatives by total cost."
        )
        st.divider()
        st.markdown("**Confidence levels**")
        st.markdown(
            "- ✓ **Exact** — identical identifier (GTIN/model)\n"
            "- ◉ **High** — same product, high similarity\n"
            "- ◎ **Medium** — likely same, verify specs\n"
            "- ○ **Similar** — related product, may differ"
        )
        st.divider()
        if st.button("🗑️ Clear Cache", use_container_width=True):
            from backend.database.cache import product_cache, search_cache
            product_cache.clear()
            search_cache.clear()
            st.session_state.pop("result", None)
            st.success("Cache cleared.")
        st.divider()
        st.markdown("[GitHub](https://github.com/yourusername/BetterProduct) · Open-source · MIT")

    # ── Trigger comparison ─────────────────────────────────────────────────────
    if go and url:
        if not url.startswith("http"):
            st.error("Please enter a valid URL starting with http:// or https://")
            return

        progress = st.progress(0, text="Scraping source product…")
        try:
            from backend.engine import comparison_engine

            progress.progress(20, text="Scraping source product…")
            result = _run_async(comparison_engine.compare(url))
            progress.progress(100, text="Done!")
            progress.empty()
            st.session_state["result"] = result
        except Exception as exc:
            progress.empty()
            st.error(f"Error: {exc}")
            with st.expander("Stack trace"):
                import traceback
                st.code(traceback.format_exc())
            return

    # ── Display results ────────────────────────────────────────────────────────
    if "result" not in st.session_state:
        return

    result = st.session_state["result"]

    st.divider()
    st.subheader("📦 Source Product")
    render_source(result.source_product)

    # ── Always-visible debug panel ─────────────────────────────────────────────
    with st.expander("🔍 Search Debug Info", expanded=not result.matches):
        d1, d2, d3 = st.columns(3)
        d1.metric("Platforms Searched", len(result.debug_platforms_searched))
        d2.metric("Raw Candidates Found", result.debug_candidates_found)
        d3.metric("Matches After Scoring", len(result.matches))

        if result.debug_platforms_searched:
            st.markdown(f"**Platforms:** {', '.join(result.debug_platforms_searched)}")
        if result.debug_queries:
            st.markdown("**Queries used:**")
            for q in result.debug_queries:
                st.code(q)
        if result.errors:
            st.markdown("**Errors / warnings:**")
            for e in result.errors:
                st.warning(e)

    if not result.matches:
        st.error(
            "No matching products found. "
            f"Searched {len(result.debug_platforms_searched)} platform(s), "
            f"found {result.debug_candidates_found} candidate(s) — all below similarity threshold. "
            "Check the debug panel above for details."
        )
        return

    # Summary metrics
    st.divider()
    st.subheader("📊 Summary")
    mc1, mc2, mc3, mc4 = st.columns(4)
    mc1.metric("Platforms Searched", " · ".join(p.title() for p in result.debug_platforms_searched) or "—")
    mc2.metric("Alternatives Found", len(result.matches))
    src_cur = result.source_product.currency or "USD"
    mc3.metric(
        "Max Savings",
        _fmt(result.total_savings, src_cur) if result.total_savings and result.total_savings > 0 else "—",
    )
    mc4.metric("Search Time", f"{result.search_time_seconds:.1f}s")

    # Recommendation cards
    if result.cheapest_exact or result.best_value:
        st.subheader("✅ Recommendations")
        rc1, rc2 = st.columns(2)
        with rc1:
            if result.cheapest_exact:
                m = result.cheapest_exact.match
                t = m.total_cost or m.price
                platform_val = m.platform if isinstance(m.platform, str) else m.platform.value
                st.success(
                    f"**💰 Cheapest Exact Match**\n\n"
                    f"{m.title[:60]}…\n\n"
                    f"**{_fmt(t, m.currency or 'USD')}** on {platform_val.title()}"
                )
        with rc2:
            if result.best_value:
                m = result.best_value.match
                t = m.total_cost or m.price
                platform_val = m.platform if isinstance(m.platform, str) else m.platform.value
                st.info(
                    f"**⭐ Best Overall Value**\n\n"
                    f"{m.title[:60]}…\n\n"
                    f"**{_fmt(t, m.currency or 'USD')}** on {platform_val.title()}"
                )

    # Tabs
    st.divider()
    st.subheader("🔄 All Alternatives")

    exact = [m for m in result.matches if (m.confidence if isinstance(m.confidence, str) else m.confidence.value) == "exact"]
    high  = [m for m in result.matches if (m.confidence if isinstance(m.confidence, str) else m.confidence.value) == "high"]
    cheaper = sorted(
        [m for m in result.matches if m.savings_amount and m.savings_amount > 0],
        key=lambda x: -(x.savings_amount or 0),
    )

    tab_all, tab_exact, tab_high, tab_cheap = st.tabs([
        f"All ({len(result.matches)})",
        f"Exact ({len(exact)})",
        f"High Confidence ({len(high)})",
        f"Cheaper ({len(cheaper)})",
    ])
    with tab_all:
        render_results_list(result.matches)
    with tab_exact:
        render_results_list(exact)
    with tab_high:
        render_results_list(high)
    with tab_cheap:
        render_results_list(cheaper)

    if result.errors:
        with st.expander("⚠️ Warnings / Partial Errors"):
            for e in result.errors:
                st.warning(e)

    st.divider()
    st.markdown(
        "<center><small>BetterProduct is open-source (MIT). "
        "Prices are scraped in real-time and may vary. "
        "Always confirm the final price on the retailer's site before purchasing.</small></center>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
