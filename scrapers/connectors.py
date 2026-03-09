from __future__ import annotations

from dataclasses import replace

from scrapers.eslintherok import ContentRecord, normalize_records


def mock_records(limit: int | None = None) -> list[ContentRecord]:
    sample = [
        {
            "url": "https://example.local/mock/colors",
            "title": "Textbook 1 - Unit 1 - red",
            "description": "basic color vocab",
        },
        {
            "url": "https://example.local/mock/classroom-language",
            "title": "Textbook 1 - Unit 2 - Can I go to the bathroom?",
            "description": "classroom expression",
        },
        {
            "url": "https://example.local/mock/animal-quiz",
            "title": "Textbook 2 - Unit 1 - What animal is this?",
            "description": "animal question prompt",
        },
        {
            "url": "https://example.local/mock/phonics-s",
            "title": "Textbook 2 - Unit 3 - Short a sound",
            "description": "phonics awareness",
        },
    ]
    if limit is not None:
        sample = sample[:limit]
    records = normalize_records(sample)
    return [replace(record, source_site="mock") for record in records]
