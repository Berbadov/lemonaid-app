# lemonaid-app

Second-hand automobile ad analyzer focused on possible issues (engine, powertrain, body, manufacturing quality, and chronic defects).

## Current MVP Scope

1. Scrape issue-reference pages from carchecker.pro using Scrapy with strict compliance controls.
2. Persist structured data in SQLite for retrieval and analysis.
3. Build a local vector index (Chroma) for RAG context.
4. Expose local analysis API via FastAPI.
5. Provide a Chrome extension popup that analyzes the currently open ad page.

## Repository Structure

- `api/` FastAPI service and request/response schemas.
- `extension/` Chrome extension (Manifest V3, popup, content extractor, background worker).
- `rag/` retrieval and DeepSeek analyzer logic.
- `scrapers/` Scrapy project for carchecker.pro issue scraping.
- `scripts/` helper scripts for DB init, crawling, and vector indexing.
- `storage/` SQLAlchemy models and SQLite session setup.
- `tests/` smoke tests.

## Compliance Defaults

This project starts with strict scraping defaults:

- `ROBOTSTXT_OBEY=true`
- bounded concurrency
- download delay and AutoThrottle enabled
- retries only for transient HTTP failures

Adjust values in `.env` only after confirming target-site policy and legal requirements.

## Quick Start

### 1) Create and activate virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2) Install dependencies

```powershell
pip install -r requirements.txt
```

### 3) Configure environment

```powershell
Copy-Item .env.example .env
```

Set your `DEEPSEEK_API_KEY` in `.env` when ready.

### 4) Initialize SQLite tables

```powershell
python scripts/init_db.py
```

### 5) Run the carchecker scraper

```powershell
python scripts/run_scraper.py
```

Targeted brand recrawl (example):

```powershell
python scripts/run_scraper.py --brand alfa_romeo
```

Expanded crawl from repo root (same spider, explicit settings module):

```powershell
$env:PYTHONPATH='d:/lemonaid-app/scrapers'
$env:SCRAPY_SETTINGS_MODULE='car_scraper.settings'
& "d:/lemonaid-app/.venv/Scripts/python.exe" -m scrapy crawl carchecker_issues -s LOG_LEVEL=INFO
```

### 6) Build vector index from scraped issue references

```powershell
python scripts/index_issue_references.py
```

Generate scrape quality report:

```powershell
python scripts/scrape_quality_report.py --output reports/scrape_quality.json
```

### 7) Start local API

```powershell
uvicorn api.main:app --reload
```

Health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Issue dataset stats:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/stats/issues
```

### 8) Load Chrome extension

1. Open Chrome and go to `chrome://extensions`.
2. Enable Developer mode.
3. Click Load unpacked.
4. Select the `extension/` folder.
5. Open a supported ad page and click Analyze Current Page in the popup.

## API Example

```json
POST /analyze
{
	"listing_url": "https://www.sahibinden.com/ilan/...",
	"ad_metadata": {
		"source": "sahibinden.com",
		"title": "2017 model example ad",
		"make": "Renault",
		"model": "Clio",
		"year": 2017,
		"mileage_km": 98000,
		"price_amount": 840000,
		"currency": "TRY",
		"description": "..."
	}
}
```

Response includes:

- summary
- risk checklist
- per-risk severity and confidence
- inspection advice

## Notes

- If `DEEPSEEK_API_KEY` is missing, the API returns a deterministic fallback analysis based on retrieved context.
- The carchecker spider uses heuristic selectors and may need tuning as the target HTML changes.
- For Turkish ad pages, metadata extraction in `extension/content.js` is currently baseline and should be expanded field-by-field during calibration.
- On Windows, `chromadb` may require MSVC Build Tools (`chroma-hnswlib` build dependency). If unavailable, API and SQL retrieval still work and vector indexing is skipped gracefully.
