from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "sqlite:///./betterproduct.db"

    # Scraping
    HEADLESS_BROWSER: bool = True
    SCRAPER_TIMEOUT: int = 30000  # ms
    MAX_SEARCH_RESULTS: int = 5

    # Cache TTL (seconds)
    PRODUCT_CACHE_TTL: int = 86400   # 24 h
    SEARCH_CACHE_TTL: int = 3600     # 1 h

    # Optional API keys
    EBAY_APP_ID: Optional[str] = None
    SCRAPERAPI_KEY: Optional[str] = None

    # Optional local LLM via Ollama
    OLLAMA_BASE_URL: Optional[str] = None
    OLLAMA_MODEL: str = "llama3"

    # Embeddings
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

    # Similarity thresholds
    SIMILARITY_THRESHOLD_EXACT: float = 0.92
    SIMILARITY_THRESHOLD_HIGH: float = 0.80
    SIMILARITY_THRESHOLD_MEDIUM: float = 0.60

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
