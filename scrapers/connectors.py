from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Iterable

from scrapers.eslintherok import ContentRecord, normalize_records, parse_games_page


@dataclass(slots=True)
class RawItem:
    url: str
    title: str
    description: str = ""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def mock_records(limit: int | None = None) -> list[ContentRecord]:
    sample = [
        {
            "url": "https://example.local/mock/colors",
            "title": "red",
            "description": "basic color vocab",
        },
        {
            "url": "https://example.local/mock/classroom-language",
            "title": "Can I go to the bathroom?",
            "description": "classroom expression",
        },
        {
            "url": "https://example.local/mock/animal-quiz",
            "title": "What animal is this?",
            "description": "animal question prompt",
        },
        {
            "url": "https://example.local/mock/phonics-s",
            "title": "Short a sound",
            "description": "phonics awareness",
        },
    ]
    if limit is not None:
        sample = sample[:limit]
    records = normalize_records(sample)
    return [replace(record, source_site="mock") for record in records]


def normalize_from_raw(raw_items: Iterable[dict[str, str]], limit: int | None = None) -> list[ContentRecord]:
    payload = list(raw_items)
    if limit is not None:
        payload = payload[:limit]
    return normalize_records(payload)


def extract_raw_from_html(html: str) -> list[dict[str, str]]:
    return parse_games_page(html)
