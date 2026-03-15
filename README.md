# 🛍️ BetterProduct

> Paste any product URL. Find the same item cheaper across Amazon, eBay, and Walmart — instantly.

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://betterproduct.streamlit.app)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
![License MIT](https://img.shields.io/badge/license-MIT-green)

---

## What it does

1. **Scrapes** the product you paste (Amazon, eBay, Walmart, or any JSON-LD site)
2. **Extracts** title, brand, model/SKU, GTIN, price, shipping, specs, rating
3. **Searches** the other two platforms for the same product
4. **Matches** results by exact identifier (GTIN / model number) then semantic similarity
5. **Ranks** by confidence level (Exact → High → Medium → Similar)
6. **Recommends** the cheapest exact match and the best overall value
7. **Explains** every result in plain English — including savings in $ and %

---

## Architecture

```
BetterProduct/
├── app.py                    # Streamlit frontend
├── api.py                    # Optional FastAPI REST API
├── backend/
│   ├── config.py             # Env-driven settings (pydantic-settings)
│   ├── models.py             # ProductData, MatchResult, ComparisonResult
│   ├── engine.py             # Orchestrator: scrape → search → match → explain
│   ├── scraper/
│   │   ├── base.py           # Playwright browser base class
│   │   ├── parser.py         # JSON-LD / microdata / OpenGraph extractor
│   │   ├── amazon.py         # Amazon scraper + search
│   │   ├── ebay.py           # eBay scraper + search
│   │   ├── walmart.py        # Walmart scraper + search (Next.js aware)
│   │   ├── generic.py        # Fallback for any JSON-LD site
│   │   └── factory.py        # Platform detection + scraper factory
│   ├── matcher/
│   │   ├── matcher.py        # Exact ID + fuzzy + embedding match logic
│   │   └── embeddings.py     # sentence-transformers wrapper (cached)
│   ├── database/
│   │   ├── schema.py         # SQLAlchemy models + engine init
│   │   └── cache.py          # Product & search result caching
│   └── explainer/
│       └── explain.py        # Template explanations + optional Ollama LLM
└── tests/
    ├── test_scraper.py
    ├── test_matcher.py
    └── demo_data.json
```

### Key design decisions

| Choice | Reason |
|--------|--------|
| Playwright (not requests) | JavaScript-rendered pages; anti-bot fingerprint masking |
| JSON-LD first, DOM fallback | Structured data is stable; DOM selectors break on redesigns |
| sentence-transformers | Local, open-source semantic matching — no API key needed |
| SQLite cache (24 h product, 1 h search) | Avoids hammering retailers; speeds up repeated lookups |
| Async + asyncio.gather | Parallel platform searches; 3× faster than sequential |

---

## Quick start

### Prerequisites
- Python 3.10+
- ~2 GB disk space (Chromium + sentence-transformer model)

### 1. Clone & install

```bash
git clone https://github.com/yourusername/BetterProduct.git
cd BetterProduct
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium      # Downloads ~150 MB Chromium
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env if you want PostgreSQL or optional API keys
```

### 3. Run

```bash
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501), paste a product URL, click **Compare**.

### Optional: Run the REST API separately

```bash
uvicorn api:app --reload --port 8000
# POST http://localhost:8000/compare  {"url": "https://amazon.com/dp/..."}
```

---

## Deploy to Streamlit Cloud (free)

1. Push this repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io) → **New app**
3. Select your repo, set **Main file path** = `app.py`
4. In **Advanced settings → Secrets**, add your `.env` values
5. Streamlit Cloud auto-installs `packages.txt` (Chromium) and `requirements.txt`
6. Click **Deploy** — done!

> **Note:** Streamlit Cloud free tier has a 1 GB RAM limit. The sentence-transformers
> model uses ~90 MB; Chromium uses ~300 MB per browser instance. Works fine on the
> free tier for light traffic.

---

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./betterproduct.db` | SQLAlchemy DB URL |
| `HEADLESS_BROWSER` | `true` | Run Chromium headlessly |
| `SCRAPER_TIMEOUT` | `30000` | Page load timeout (ms) |
| `MAX_SEARCH_RESULTS` | `5` | Max results per platform per query |
| `PRODUCT_CACHE_TTL` | `86400` | Product cache lifetime (s) |
| `SEARCH_CACHE_TTL` | `3600` | Search cache lifetime (s) |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | sentence-transformers model |
| `SIMILARITY_THRESHOLD_EXACT` | `0.92` | Score → Exact confidence |
| `SIMILARITY_THRESHOLD_HIGH` | `0.80` | Score → High confidence |
| `SIMILARITY_THRESHOLD_MEDIUM` | `0.60` | Score → Medium confidence |
| `EBAY_APP_ID` | _(optional)_ | eBay Browse API key |
| `SCRAPERAPI_KEY` | _(optional)_ | ScraperAPI key for anti-bot bypass |
| `OLLAMA_BASE_URL` | _(optional)_ | Ollama endpoint for LLM explanations |
| `OLLAMA_MODEL` | `llama3` | Ollama model name |

---

## Running tests

```bash
pytest tests/ -v
```

Tests use only the `demo_data.json` fixture — no live network calls, no Playwright.

---

## Adding a new platform

1. Create `backend/scraper/mynewplatform.py` inheriting `BaseScraper`
2. Implement `scrape_product(url)` and `search(query, max_results)`
3. Register the domain in `backend/scraper/factory.py` → `PLATFORM_DOMAINS`
4. Add the scraper class to `_scraper_map()` in `factory.py`
5. Add to `_search_all()` in `backend/engine.py`

---

## Tech stack

| Layer | Library |
|-------|---------|
| Frontend | Streamlit |
| REST API | FastAPI + Uvicorn |
| Browser automation | Playwright (Chromium) |
| HTML parsing | BeautifulSoup4 + lxml |
| Structured data | extruct (JSON-LD, microdata, OpenGraph) |
| Semantic matching | sentence-transformers (`all-MiniLM-L6-v2`) |
| Fuzzy matching | rapidfuzz |
| Caching / DB | SQLAlchemy + SQLite (PostgreSQL-compatible) |
| Settings | pydantic-settings |
| Optional LLM | Ollama (llama3 / any local model) |

---

## License

MIT — see [LICENSE](LICENSE).
