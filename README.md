# ESL Content Scraper Strategy (Ednoda-Aligned)

This repository bootstraps a **compliant, metadata-rich ESL scraping pipeline** for elementary resources that can be transformed into **Ednoda `EducationNode` records**.

## Recommended first source

Start with **ESL in the Rok** (`https://www.eslintherok.com/games`) first.

### Why this source first

1. **Lower technical friction**: public page structure is easier than app-heavy or login-gated platforms.
2. **Lower risk**: easier to operate politely (robots + request pacing) and validate terms constraints early.
3. **Fast schema proving**: lets us validate CSV + Ednoda mapping before adding complex sources.
4. **Reusable connector pattern**: same architecture can then be used for Wordwall and later candidates.

## Research constraints

I attempted to inspect `https://capstone.ednoda.com` directly from this environment, but outbound access is blocked by the proxy tunnel (HTTP 403), so plan details below are aligned from your provided model contract and best-practice ingestion patterns.

## Ednoda model alignment

Your `EducationNode` model has atomic `nodeType` values:

- `vocab`
- `expression`
- `question`
- `phonics`

This scraper pipeline should produce **atomic candidates only** at ingest time, then allow downstream jobs to compose `composite_question_answer` / `composite_dialogue` nodes as separate transformations.

## Canonical CSV contract (staging)

The scraper writes a staging CSV with ingestion-critical fields + future-ready metadata:

- `record_id` (stable deterministic ID)
- `source_site`
- `source_url`
- `source_title`
- `node_text` *(maps to Ednoda `nodeText`)*
- `node_type` *(maps to Ednoda `nodeType`)*
- `target_type` *(legacy classifier mirror)*
- `activity_type`
- `topic`
- `tags`
- `description`
- `grade_level`
- `esl_level`
- `language`
- `cefr_estimate`
- `difficulty_score`
- `complexity_score`
- `grammar_patterns`
- `source_author`
- `source_license`
- `content_hash`
- `scraped_at_utc`

## Rollout plan

### Phase 0 — Compliance + governance

- Add per-site policy file (`configs/site_policies.yaml`) including:
  - robots rules,
  - crawl-delay bounds,
  - terms review status,
  - allowed URL patterns.
- Store provenance (`source_url`, `scraped_at_utc`, `content_hash`) for auditability.

### Phase 1 — ESL in the Rok connector (now)

- Crawl index pages only, extract candidate text assets.
- Normalize into canonical CSV contract.
- Deduplicate by `content_hash` and deterministic `record_id`.

### Phase 2 — Ednoda ingestion prep

- Add classifier pass that predicts `node_type` = `vocab|expression|question|phonics`.
- Reject or quarantine low-confidence rows.
- Generate import-ready payloads for `EducationNode` creation with defaults:
  - `visibility=private`
  - `moderationStatus=pending`

### Phase 3 — Metadata enrichment

- CEFR heuristic pass (frequency + grammar complexity + length bands).
- Difficulty metrics (token count, rarity index, syntactic depth proxy).
- Grammar pattern extraction (question forms, tense markers, chunk templates).

### Phase 4 — Additional sources

- Wordwall (public pages first).
- Wayground only after terms/access review.
- Kahoot only when ToS and access boundaries permit it.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 -m scrapers.eslintherok --output data/eslintherok_games.csv --limit 100
```

## Modern scraping principles used

- robots-aware polite crawling
- bounded request pacing with jitter
- deterministic IDs and dedupe hashes
- strict separation between extraction and normalization
- provenance-first recordkeeping for moderation + audit


## Live dashboard (real-time monitoring)

A lightweight dashboard is included so you can:

- start a scrape run,
- watch run status update in real-time,
- view recently scraped nodes + metadata,
- download all persisted records as CSV.

Run:

```bash
python3 -m dashboard.server --host 0.0.0.0 --port 8080
```

Then open `http://localhost:8080`.

Data persistence uses SQLite at `data/scraper_dashboard.sqlite3`.


### Supported dashboard sources

- `eslintherok`: real web scrape (robots-aware; may be blocked by policy).
- `mock`: local synthetic records for validating dashboard/DB/export flow end-to-end.

### Dashboard API endpoints

- `POST /api/start` with JSON body `{ "source": "mock|eslintherok", "limit": 100 }`
- `GET /api/status`
- `GET /api/runs?limit=20`
- `GET /api/events?run_id=<id>&limit=100`
- `GET /api/records?limit=50&offset=0&run_id=<id>`
- `GET /download.csv` (or `/download.csv?run_id=<id>`)

## TSherpa extractor location

The TSherpa teacher-PDF extraction workflow has been moved into the dedicated `extract-textbook-content` project folder in this repository.
See `extract-textbook-content/README.md` for usage.
