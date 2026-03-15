# BetterProduct — Roadmap

## ✅ MVP (current)

- [x] Scrape any Amazon / eBay / Walmart product URL
- [x] JSON-LD structured data extraction with DOM fallback
- [x] Cross-platform search (2 queries × 3 platforms, async)
- [x] Exact identifier matching (GTIN, ASIN, model number)
- [x] Semantic similarity via sentence-transformers
- [x] Confidence classification (Exact / High / Medium / Low)
- [x] Savings calculation ($ and %)
- [x] Template-based plain-English explanations
- [x] SQLite cache (products 24 h, searches 1 h)
- [x] Streamlit UI with tabs, badges, recommendation cards
- [x] FastAPI REST endpoint
- [x] Streamlit Cloud deployment support (`packages.txt`)
- [x] pytest unit tests + demo data fixture

---

## 🔜 v1.1 — Quality & Coverage

- [ ] **Best Buy scraper** (electronics — high search volume)
- [ ] **Target scraper**
- [ ] **Google Shopping aggregator** — search Google Shopping for broader coverage
- [ ] **eBay Browse API** integration (cleaner than scraping, free tier available)
- [ ] **Price history chart** — store historical prices in DB and plot with Plotly
- [ ] **Seller reputation score** — pull seller feedback % for eBay / Amazon marketplace
- [ ] **Currency detection & conversion** — auto-detect non-USD pages, convert for comparison
- [ ] **Shipping estimation** — prompt user for ZIP code and compute real shipping cost

---

## 🔜 v1.2 — Reliability & Scale

- [ ] **ScraperAPI / Zyte fallback** — when Playwright gets blocked, retry via proxy API
- [ ] **Redis cache** — replace SQLite cache for multi-instance deployments
- [ ] **PostgreSQL support** — already wired via `DATABASE_URL`; add Alembic migrations
- [ ] **Rate limiting** — per-IP limit on the FastAPI endpoint
- [ ] **Background job queue** — Celery / RQ to process comparisons async (webhook / SSE)
- [ ] **Retry logic** — exponential backoff for failed scrape attempts
- [ ] **Structured logging** — replace print/exceptions with structlog + log aggregation

---

## 🔜 v2.0 — Product Intelligence

- [ ] **Price alert** — user enters email, gets notified when price drops below threshold
- [ ] **Spec normalisation** — use local LLM (Ollama) to normalise heterogeneous spec tables into a unified schema (e.g., "battery_life_hours": 30)
- [ ] **Product graph** — detect product variants (color, storage) and cluster them
- [ ] **Review sentiment** — scrape top reviews, run local sentiment analysis, surface pros/cons
- [ ] **"Is this a good deal?" score** — compare against historical price + competitor prices
- [ ] **Browser extension** — inject BetterProduct panel into Amazon/eBay/Walmart product pages
- [ ] **Mobile PWA** — Streamlit PWA config or separate React frontend

---

## 🔜 v3.0 — Monetisation & Community

- [ ] **Affiliate link rewriting** — optionally append affiliate tags to outbound links
- [ ] **User accounts** — save searches, set alerts, view history
- [ ] **Community price submissions** — crowdsourced price corrections + deal submissions
- [ ] **API as a service** — tiered API keys, rate-limited free tier + paid plans
- [ ] **Admin dashboard** — monitor scrape success rates, cache hit rates, platform uptime

---

## Known limitations (MVP)

| Issue | Workaround |
|-------|-----------|
| Amazon aggressively blocks headless Chromium | Retry with stealth mode; consider ScraperAPI key for production |
| Walmart search results need JS rendering | Playwright waits for `[data-item-id]` selector; works in most cases |
| sentence-transformers cold start ~5 s | Model cached after first load; show spinner in UI |
| No real-time price verification | Cache TTL is 1 h for searches; show "verified at" timestamp |
| Free Streamlit Cloud has 1 GB RAM | Works for single-user demo; upgrade tier for production traffic |
