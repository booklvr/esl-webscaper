from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from scrapers.common import PoliteHttpClient
from scrapers.connectors import extract_raw_from_html, mock_records, normalize_from_raw
from scrapers.eslintherok import ContentRecord, GAMES_URL

EventCallback = Callable[[str], None]


@dataclass(slots=True)
class ScrapeResult:
    source: str
    records: list[ContentRecord]


class UnsupportedSourceError(ValueError):
    pass


def scrape_source(source: str, limit: int | None = None, on_event: EventCallback | None = None) -> ScrapeResult:
    notify = on_event or (lambda _msg: None)

    if source == "mock":
        notify("Generating mock records for local testing")
        return ScrapeResult(source=source, records=mock_records(limit=limit))

    if source == "eslintherok":
        notify(f"Fetching source page: {GAMES_URL}")
        client = PoliteHttpClient()
        try:
            response = client.get(GAMES_URL)
            notify("Fetched games page successfully")
        finally:
            client.close()

        raw_items = extract_raw_from_html(response.text)
        notify(f"Parsed {len(raw_items)} raw links from source page")
        records = normalize_from_raw(raw_items=raw_items, limit=limit)
        notify(f"Normalized {len(records)} records")
        return ScrapeResult(source=source, records=records)

    raise UnsupportedSourceError(f"Unsupported source: {source}")
