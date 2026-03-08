# Ednoda Ingestion Plan for Scraped ESL Content

This document defines how staging CSV rows become Ednoda `EducationNode` records.

## 1) Staging CSV -> EducationNode mapping

| CSV Field | EducationNode Field | Notes |
|---|---|---|
| `node_text` | `nodeText` | Required for useful atomic nodes |
| `node_type` | `nodeType` | Must be one of `vocab|expression|question|phonics` |
| `source_url` | N/A (provenance table or metadata JSON) | Keep for traceability |
| `source_site` | N/A (provenance table or metadata JSON) | Keep for licensing/moderation |
| `record_id` | N/A (external ID) | Useful for idempotent imports |

Recommended create defaults:

- `visibility = private`
- `moderationStatus = pending`
- `ownerUserId = null` (or service user)

## 2) Validation gates before insert

1. `node_text` non-empty after trim.
2. `node_type` in allowed atomic enum.
3. language is expected (currently `en`).
4. duplicate control by `content_hash` and normalized `node_text`.
5. source policy check passed for originating site.

## 3) Suggested moderation workflow

- Auto-ingest rows as private/pending.
- Human or rubric review step approves/rejects.
- Public visibility only after moderation.

## 4) Future metadata extensions

Metadata fields to compute and store alongside nodes (or in a side table):

- CEFR estimate
- lexical difficulty
- syntactic complexity
- grammar pattern tags
- curriculum alignment tags

## 5) Site onboarding checklist

1. Terms/robots review documented.
2. Parser fixtures added from sample HTML snapshots.
3. Deduping quality evaluated on initial scrape.
4. Metadata extraction measured (null-rate and confidence).
5. Import dry-run against Ednoda staging DB.
