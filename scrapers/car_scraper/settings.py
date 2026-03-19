from __future__ import annotations

import os
import sys
from pathlib import Path

BOT_NAME = "lemonaid_issue_scraper"

SPIDER_MODULES = ["car_scraper.spiders"]
NEWSPIDER_MODULE = "car_scraper.spiders"

# Strict-compliance defaults.
ROBOTSTXT_OBEY = os.getenv("SCRAPER_ROBOTSTXT_OBEY", "true").lower() == "true"

CONCURRENT_REQUESTS = int(os.getenv("SCRAPER_CONCURRENT_REQUESTS", "8"))
CONCURRENT_REQUESTS_PER_DOMAIN = min(CONCURRENT_REQUESTS, 8)
DOWNLOAD_DELAY = float(os.getenv("SCRAPER_DOWNLOAD_DELAY", "0.35"))
RANDOMIZE_DOWNLOAD_DELAY = True
RETRY_ENABLED = True
RETRY_TIMES = 3
RETRY_HTTP_CODES = [429, 500, 502, 503, 504, 522, 524, 408]

AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = float(os.getenv("SCRAPER_AUTOTHROTTLE_START_DELAY", "0.3"))
AUTOTHROTTLE_MAX_DELAY = float(os.getenv("SCRAPER_AUTOTHROTTLE_MAX_DELAY", "6.0"))
AUTOTHROTTLE_TARGET_CONCURRENCY = 1.5

DEFAULT_REQUEST_HEADERS = {
    "User-Agent": os.getenv(
        "SCRAPER_USER_AGENT",
        "LemonaidResearchBot/0.1 (+contact@example.com)",
    )
}

ITEM_PIPELINES = {
    "car_scraper.pipelines.SQLiteIssuePipeline": 300,
}

LOG_LEVEL = "INFO"

# Allow scraper package to import project modules from repo root.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))
