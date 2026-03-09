from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from scrapers.common import PoliteHttpClient
from scrapers.connectors import mock_records
from scrapers.eslintherok import ContentRecord, GAMES_URL, scrape_records

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
        notify(f"Fetching source index page: {GAMES_URL}")
        client = PoliteHttpClient()
        try:
            records = scrape_records(client=client, limit=limit, on_event=notify)
        finally:
            client.close()

        notify(f"Engine returning {len(records)} records")
        return ScrapeResult(source=source, records=records)

    raise UnsupportedSourceError(f"Unsupported source: {source}")
