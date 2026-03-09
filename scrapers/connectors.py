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
    """
    Enhanced mock data with real ESL textbook content.
    Each record has textbook source + unit metadata in tags field.
    """
    sample = [
        # Vocabulary items from textbooks
        {
            "url": "https://example.local/vocab/colors-beginner",
            "title": "red",
            "description": "Basic color vocabulary",
        },
        {
            "url": "https://example.local/vocab/family-unit2",
            "title": "mother",
            "description": "Family vocabulary",
        },
        {
            "url": "https://example.local/vocab/animals-unit3",
            "title": "cat",
            "description": "Animal vocabulary",
        },
        {
            "url": "https://example.local/vocab/food-unit5",
            "title": "apple",
            "description": "Food and drink vocabulary",
        },
        # Expressions
        {
            "url": "https://example.local/expr/classroom-unit1",
            "title": "Can I go to the bathroom?",
            "description": "Classroom language expressions",
        },
        {
            "url": "https://example.local/expr/greetings-unit1",
            "title": "How are you?",
            "description": "Common greetings and responses",
        },
        {
            "url": "https://example.local/expr/shopping-unit8",
            "title": "How much does this cost?",
            "description": "Shopping expressions",
        },
        # Questions
        {
            "url": "https://example.local/q/animals-unit3",
            "title": "What animal is this?",
            "description": "Animal identification questions",
        },
        {
            "url": "https://example.local/q/comprehension-unit2",
            "title": "Where does the main character live?",
            "description": "Reading comprehension questions",
        },
        {
            "url": "https://example.local/q/listening-unit4",
            "title": "What time does the store open?",
            "description": "Listening comprehension questions",
        },
        # Phonics
        {
            "url": "https://example.local/phonics/short-a",
            "title": "Short 'a' sound (cat, hat, bat)",
            "description": "Phonics - vowel sounds",
        },
        {
            "url": "https://example.local/phonics/consonant-s",
            "title": "Consonant 's' (sun, sit, six)",
            "description": "Phonics - consonant sounds",
        },
        {
            "url": "https://example.local/phonics/blend-st",
            "title": "Consonant blend 'st' (stop, stand, story)",
            "description": "Phonics - consonant blends",
        },
        # More complex expressions and questions
        {
            "url": "https://example.local/expr/past-tense-unit6",
            "title": "I went to the store yesterday",
            "description": "Past tense expressions",
        },
        {
            "url": "https://example.local/q/tense-practice-unit6",
            "title": "Did you go to school?",
            "description": "Past tense yes/no questions",
        },
        {
            "url": "https://example.local/vocab/weather-unit7",
            "title": "sunny",
            "description": "Weather vocabulary",
        },
    ]
    
    if limit is not None:
        sample = sample[:limit]
    
    records = normalize_records(sample)
    
    # Add metadata about textbooks/units to the tags field
    enhanced_records = []
    for i, record in enumerate(records):
        source_item = sample[i]
        
        # Extract textbook info from URL
        textbook = "Unknown"
        unit = "Unknown"
        
        if "/vocab/" in source_item["url"]:
            parts = source_item["url"].split("/vocab/")[1].split("-")
            topic = parts[0]
            if "unit" in source_item["url"]:
                unit = source_item["url"].split("unit")[1]
            textbook = "ESL Vocabulary Book"
        elif "/expr/" in source_item["url"]:
            parts = source_item["url"].split("/expr/")[1].split("-")
            topic = parts[0]
            if "unit" in source_item["url"]:
                unit = source_item["url"].split("unit")[1]
            textbook = "ESL Expression Guide"
        elif "/q/" in source_item["url"]:
            parts = source_item["url"].split("/q/")[1].split("-")
            topic = parts[0]
            if "unit" in source_item["url"]:
                unit = source_item["url"].split("unit")[1]
            textbook = "ESL Comprehension"
        elif "/phonics/" in source_item["url"]:
            textbook = "ESL Phonics"
            unit = source_item["url"].split("/phonics/")[1]
        
        # Build tags with metadata
        tags = f"textbook:{textbook},unit:unit{unit}" if unit != "Unknown" else f"textbook:{textbook}"
        
        enhanced = replace(
            record,
            source_site="mock",
            tags=tags,
            topic=source_item["description"],
        )
        enhanced_records.append(enhanced)
    
    return enhanced_records


def normalize_from_raw(raw_items: Iterable[dict[str, str]], limit: int | None = None) -> list[ContentRecord]:
    payload = list(raw_items)
    if limit is not None:
        payload = payload[:limit]
    return normalize_records(payload)


def extract_raw_from_html(html: str) -> list[dict[str, str]]:
    return parse_games_page(html)
