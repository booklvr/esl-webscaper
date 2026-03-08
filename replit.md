# ESL Content Scraper Dashboard

## Overview
A Python-based web scraper pipeline and real-time monitoring dashboard for ESL (English as a Second Language) content. Scrapes content from ESL sites and transforms it into Ednoda `EducationNode`-compatible records.

## Architecture
- **Language**: Python 3.12
- **No third-party dependencies** — uses only Python stdlib
- **Database**: SQLite at `data/scraper_dashboard.sqlite3`
- **Web server**: Python's built-in `http.server.ThreadingHTTPServer`

## Project Layout
```
dashboard/       - Web dashboard server and SQLite DB layer
  server.py      - HTTP server + HTML dashboard + API endpoints
  db.py          - DashboardDB class (SQLite schema + queries)
scrapers/        - Scraper engine and connectors
  engine.py      - Central dispatch: scrape_source()
  eslintherok.py - ESL in the Rok connector + ContentRecord dataclass
  connectors.py  - Shared connector utilities
  common.py      - Common scraping helpers
data/            - SQLite database (auto-created at runtime)
tests/           - Test suite
docs/            - Ingestion planning docs
```

## Running the App
The dashboard runs on port 5000:
```bash
python3 -m dashboard.server --host 0.0.0.0 --port 5000
```

## Dashboard API
- `POST /api/start` — `{ "source": "mock|eslintherok", "limit": 100 }`
- `GET /api/status` — Latest run + total record count
- `GET /api/runs?limit=20` — Recent scrape runs
- `GET /api/events?run_id=<id>&limit=100` — Events for a run
- `GET /api/records?limit=50&offset=0&run_id=<id>` — Scraped records
- `GET /download.csv` — Download all records as CSV

## Supported Sources
- `mock` — Synthetic records for testing the dashboard flow
- `eslintherok` — Live scrape of eslintherok.com (robots-aware, rate-limited)

## Workflow
- **Start application**: `python3 -m dashboard.server --host 0.0.0.0 --port 5000`
- Port: 5000 (webview)

## Deployment
- Target: `vm` (always-running, maintains SQLite state)
- Run: `python3 -m dashboard.server --host 0.0.0.0 --port 5000`
