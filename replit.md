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
  server.py      - HTTP server + modern HTML dashboard + API endpoints
  db.py          - DashboardDB class (SQLite schema + queries)
scrapers/        - Scraper engine and connectors
  engine.py      - Central dispatch: scrape_source()
  eslintherok.py - ESL in the Rok connector + ContentRecord dataclass
  connectors.py  - Shared connector utilities (mock records, normalizers)
  common.py      - Common scraping helpers (PoliteHttpClient, robots.txt aware)
data/            - SQLite database (auto-created at runtime)
tests/           - Test suite
docs/            - Ingestion planning docs
```

## Running the App
The dashboard runs on port 5000 with modern UI:
```bash
python3 -m dashboard.server --host 0.0.0.0 --port 5000
```
Open http://localhost:5000 to access the dashboard.

## Dashboard Features
- Modern, responsive UI with gradient background and clean card layout
- Real-time run status, statistics, and record display
- Source selector (Mock test data or ESL in the Rok)
- Optional limit parameter for scrape jobs
- CSV export of all records
- Live event log for scrape runs
- Automatic refresh every 2 seconds

## API Endpoints
- `POST /api/start` — Start scrape: `{ "source": "mock|eslintherok", "limit": 100 }`
- `GET /api/status` — Latest run + total record count
- `GET /api/runs?limit=20` — Recent scrape runs
- `GET /api/events?run_id=<id>&limit=100` — Events for a run
- `GET /api/records?limit=50&offset=0&run_id=<id>` — Scraped records
- `GET /download.csv` — Download all records as CSV

## Supported Sources
- `mock` — Synthetic test records (always works, good for testing flow)
- `eslintherok` — Live scrape of https://www.eslintherok.com/games (robots-aware, rate-limited)

## Scraping Features
- **Polite crawling**: Respects robots.txt and enforces rate limiting (1-2.5 second delays)
- **Deterministic IDs**: Content is deduplicated by stable ID generation
- **Content hashing**: Tracks content changes via SHA256 hashing
- **Atomic records**: Creates individual vocab, expression, question, or phonics nodes
- **Provenance tracking**: Records source URL, timestamp, and content hash for audit trail

## Implementation Status
- ✅ Workflow configured on port 5000
- ✅ Dashboard modernized with clean UI
- ✅ Mock scraper functional (generates test records)
- ✅ ESL in the Rok connector working (site accessible)
- ✅ Database schema and queries implemented
- ✅ CSV export functional
- ✅ Real-time event logging implemented
- ✅ Deployment configured for VM (always-running)

## Known Design Characteristics
- Some metadata fields are intentionally empty (topic, grade_level, esl_level, cefr_estimate)
  - These are populated in Phase 3 (Metadata enrichment) as separate transformation steps
- Mock data provides 4 test records covering vocab, expression, question, and phonics types
- SQLite used for simplicity; easily swappable for PostgreSQL if needed
- Threading used for background scrape jobs to prevent blocking UI

## Workflow & Deployment
- **Workflow**: `Start application` runs on port 5000 with webview output
- **Deployment Target**: VM (always-running for maintaining SQLite state)
- **Run Command**: `python3 -m dashboard.server --host 0.0.0.0 --port 5000`
