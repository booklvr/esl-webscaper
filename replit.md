# ESL Content Scraper Dashboard

## Overview
A Python-based web scraper pipeline and real-time monitoring dashboard for ESL (English as a Second Language) content. Scrapes content from ESL sites and transforms it into Ednoda `EducationNode`-compatible records with textbook/unit metadata.

## Architecture
- **Language**: Python 3.12
- **No heavy third-party dependencies** — uses Python stdlib + Playwright (for future headless browser scraping)
- **Database**: SQLite at `data/scraper_dashboard.sqlite3`
- **Web server**: Python's built-in `http.server.ThreadingHTTPServer`

## Project Layout
```
dashboard/       - Web dashboard server and SQLite DB layer
  server.py      - Modern HTTP server with responsive HTML dashboard + API endpoints
  db.py          - DashboardDB class (SQLite schema + queries)
scrapers/        - Scraper engine and connectors
  engine.py      - Central dispatch: scrape_source()
  eslintherok.py - ESL in the Rok connector + ContentRecord dataclass
  connectors.py  - Shared connector utilities (enhanced mock records with textbook metadata)
  common.py      - Common scraping helpers (PoliteHttpClient, robots.txt aware)
data/            - SQLite database (auto-created at runtime)
tests/           - Test suite
docs/            - Ingestion planning docs
```

## Running the App
The dashboard runs on port 5000 with modern responsive UI:
```bash
python3 -m dashboard.server --host 0.0.0.0 --port 5000
```
Open http://localhost:5000 to access the dashboard.

## Dashboard Features
- Modern, responsive UI with gradient background and clean card layout
- Real-time run status, statistics, and record display
- Source selector (Mock test data with real ESL content or live ESL in the Rok)
- Optional limit parameter for scrape jobs
- CSV export of all records
- Live event log for scrape runs
- Automatic refresh every 2 seconds
- Records display textbook source and unit metadata

## API Endpoints
- `POST /api/start` — Start scrape: `{ "source": "mock|eslintherok", "limit": 100 }`
- `GET /api/status` — Latest run + total record count
- `GET /api/runs?limit=20` — Recent scrape runs
- `GET /api/events?run_id=<id>&limit=100` — Events for a run
- `GET /api/records?limit=50&offset=0&run_id=<id>` — Scraped records with metadata
- `GET /download.csv` — Download all records as CSV

## Supported Sources

### Mock (Ready Now)
- **Status**: ✅ Fully functional
- **Content**: 16+ synthetic ESL educational records
- **Features**: 
  - Real textbook metadata (textbook name, unit number)
  - Multiple content types: vocabulary, expressions, questions, phonics
  - Deterministic IDs and content hashing
  - CSV export works perfectly
- **Use for**: Testing flow, development, demonstrations

### ESL in the Rok (Needs Enhancement)
- **Status**: ⚠️ Partially implemented
- **Current State**: Can scrape game index and menu items
- **Challenge**: Site uses Next.js with JavaScript-rendered content
- **Solution Needed**: Headless browser automation (Playwright ready, needs system libraries)
- **Roadmap**:
  - Phase 1: Set up headless Chrome in environment
  - Phase 2: Parse individual game pages for actual vocabulary/expressions
  - Phase 3: Extract textbook/unit metadata from page content
  - Phase 4: Handle rate limiting and caching

## Educational Content Structure

### Record Types
Each ContentRecord contains:
- `node_type`: One of `vocab`, `expression`, `question`, `phonics`
- `node_text`: The actual ESL content (word, phrase, or question)
- `tags`: Machine-readable metadata (format: `textbook:Name,unit:unitN`)
- `topic`: Human-readable category
- `source_url`: Original source page
- `content_hash`: SHA256 for deduplication
- `scraped_at_utc`: Timestamp for audit trail

### Mock Data Examples
- **Vocabulary**: "red", "mother", "cat", "apple", "sunny" (with textbook source)
- **Expressions**: "Can I go to the bathroom?", "How are you?", "How much does this cost?"
- **Questions**: "What animal is this?", "Where does the main character live?"
- **Phonics**: "Short 'a' sound", "Consonant 's'", "Consonant blend 'st'"

## Implementation Status
- ✅ Workflow configured on port 5000 (webview)
- ✅ Modern, responsive dashboard UI
- ✅ Mock scraper functional with real ESL content structure
- ✅ Textbook/unit metadata in tags field
- ✅ Database schema and queries implemented
- ✅ CSV export functional with all metadata
- ✅ Real-time event logging
- ✅ Deployment configured for VM (always-running)
- ⚠️ Live ESL in the Rok scraping (blocked by environment limitations on headless Chrome)

## Known Limitations & Design Notes
- **Headless browser**: Playwright installed but requires system libraries (libnspr4.so) not available in Replit environment
  - Workaround: Can be deployed to full VM where system dependencies available
  - Alternative: Could use third-party browser automation API (ScraperAPI, Bright Data)
- **Empty metadata fields**: Some fields intentionally sparse pending Phase 3 enrichment (CEFR estimates, difficulty scores)
- **Next.js sites**: eslintherok.com uses Next.js with client-side rendering - static HTML parsing insufficient
- **Content in HTML**: Actual ESL content is loaded dynamically by JavaScript, not present in initial HTML

## Testing the System
1. **Start mock scrape**:
   - Click "Start Scrape" with Mock source
   - View real ESL content with textbook metadata
   - Records appear within 2 seconds
   - Download CSV to verify all fields

2. **Test live source** (when headless browser available):
   - Change source to "ESL in the Rok"
   - Click "Start Scrape"
   - Watch event log for progress
   - Records will contain actual game content + unit info

## Dependencies
```
Python 3.12
playwright (for future live scraping)
```

## Workflow & Deployment
- **Workflow**: `Start application` runs on port 5000 with webview output
- **Deployment Target**: VM (always-running for maintaining SQLite state)
- **Run Command**: `python3 -m dashboard.server --host 0.0.0.0 --port 5000`

## Next Steps for Live Scraping
To enable ESL in the Rok live scraping:
1. Deploy to environment with full system library support
2. Implement Playwright-based game page parser
3. Extract content from rendered HTML
4. Add unit/textbook metadata extraction
5. Test rate limiting (currently set to 1-2.5s delays)
