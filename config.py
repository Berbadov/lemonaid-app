from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class AppConfig:
    sqlite_path: Path = Path(os.getenv("SQLITE_PATH", "data/lemonaid.db"))
    chroma_persist_dir: Path = Path(os.getenv("CHROMA_PERSIST_DIR", "chroma_db"))
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")

    analyzer_api_url: str = os.getenv("ANALYZER_API_URL", "http://127.0.0.1:8000")

    scraper_user_agent: str = os.getenv(
        "SCRAPER_USER_AGENT",
        "search/0.1 (+contact@example.com)",
    )
    scraper_concurrent_requests: int = int(os.getenv("SCRAPER_CONCURRENT_REQUESTS", "8"))
    scraper_download_delay: float = float(os.getenv("SCRAPER_DOWNLOAD_DELAY", "0.35"))
    scraper_autothrottle_start_delay: float = float(
        os.getenv("SCRAPER_AUTOTHROTTLE_START_DELAY", "0.3")
    )
    scraper_autothrottle_max_delay: float = float(
        os.getenv("SCRAPER_AUTOTHROTTLE_MAX_DELAY", "6.0")
    )
    scraper_robotstxt_obey: bool = os.getenv("SCRAPER_ROBOTSTXT_OBEY", "true").lower() == "true"


SETTINGS = AppConfig()


def ensure_data_dirs() -> None:
    """Create local storage directories used by SQLite and Chroma."""
    sqlite_parent = (ROOT_DIR / SETTINGS.sqlite_path).resolve().parent
    sqlite_parent.mkdir(parents=True, exist_ok=True)

    chroma_dir = (ROOT_DIR / SETTINGS.chroma_persist_dir).resolve()
    chroma_dir.mkdir(parents=True, exist_ok=True)
