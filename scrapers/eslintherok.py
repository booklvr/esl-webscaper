from __future__ import annotations

import argparse
import csv
import hashlib
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin

from scrapers.common import PoliteHttpClient

GAMES_URL = "https://www.eslintherok.com/games"


@dataclass(slots=True)
class ContentRecord:
    record_id: str
    source_site: str
    source_url: str
    source_title: str
    node_text: str
    node_type: str
    target_type: str
    activity_type: str
    topic: str
    tags: str
    description: str
    grade_level: str
    esl_level: str
    language: str
    cefr_estimate: str
    difficulty_score: str
    complexity_score: str
    grammar_patterns: str
    source_author: str
    source_license: str
    content_hash: str
    scraped_at_utc: str


QUESTION_STARTERS = ("what ", "where ", "who ", "when ", "why ", "how ", "do ", "does ", "is ", "are ")


class AnchorExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.anchors: list[tuple[str, str]] = []
        self._current_href: str | None = None
        self._current_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        attrs_dict = dict(attrs)
        self._current_href = (attrs_dict.get("href") or "").strip()
        self._current_text = []

    def handle_data(self, data: str) -> None:
        if self._current_href is not None:
            self._current_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or self._current_href is None:
            return
        title = " ".join("".join(self._current_text).split())
        if self._current_href and title:
            self.anchors.append((self._current_href, title))
        self._current_href = None
        self._current_text = []


def infer_target_type(text: str) -> str:
    normalized = text.strip().lower()
    if not normalized:
        return "unknown"
    if "?" in normalized or normalized.startswith(QUESTION_STARTERS):
        return "question"
    if "phonics" in normalized or "letter" in normalized or "sound" in normalized:
        return "phonics"
    if " " in normalized and len(normalized.split()) >= 3:
        return "expression"
    return "vocab"


def stable_id(source_url: str, title: str) -> str:
    digest = hashlib.sha256(f"{source_url}|{title}".encode("utf-8")).hexdigest()
    return digest[:16]


def content_hash(node_text: str, node_type: str) -> str:
    return hashlib.sha256(f"{node_type}|{node_text.strip().lower()}".encode("utf-8")).hexdigest()


def parse_games_page(html: str, base_url: str = GAMES_URL) -> list[dict[str, str]]:
    extractor = AnchorExtractor()
    extractor.feed(html)

    results: list[dict[str, str]] = []
    seen_links: set[str] = set()

    for href, title in extractor.anchors:
        full_url = urljoin(base_url, href)
        if "eslintherok.com" not in full_url:
            continue
        if full_url in seen_links:
            continue

        seen_links.add(full_url)
        results.append({"url": full_url, "title": title, "description": ""})

    return results


def normalize_records(raw_items: Iterable[dict[str, str]]) -> list[ContentRecord]:
    now = datetime.now(timezone.utc).isoformat()
    records: list[ContentRecord] = []

    for item in raw_items:
        title = item.get("title", "").strip()
        source_url = item.get("url", "").strip()
        description = item.get("description", "").strip()
        if not title or not source_url:
            continue

        node_text = title
        node_type = infer_target_type(node_text)

        records.append(
            ContentRecord(
                record_id=stable_id(source_url, title),
                source_site="eslintherok",
                source_url=source_url,
                source_title=title,
                node_text=node_text,
                node_type=node_type,
                target_type=node_type,
                activity_type="game",
                topic="",
                tags="",
                description=description,
                grade_level="",
                esl_level="",
                language="en",
                cefr_estimate="",
                difficulty_score="",
                complexity_score="",
                grammar_patterns="",
                source_author="",
                source_license="",
                content_hash=content_hash(node_text=node_text, node_type=node_type),
                scraped_at_utc=now,
            )
        )

    unique_records = {record.record_id: record for record in records}
    return list(unique_records.values())


def write_csv(records: list[ContentRecord], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(asdict(records[0]).keys()) if records else list(ContentRecord.__annotations__.keys())

    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow(asdict(record))


def run(output: Path, limit: int | None = None) -> int:
    client = PoliteHttpClient()
    try:
        response = client.get(GAMES_URL)
    finally:
        client.close()

    raw_items = parse_games_page(response.text)
    if limit:
        raw_items = raw_items[:limit]

    records = normalize_records(raw_items)
    write_csv(records, output)
    return len(records)


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape ESL in the Rok games into CSV")
    parser.add_argument("--output", type=Path, default=Path("data/eslintherok_games.csv"))
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    count = run(output=args.output, limit=args.limit)
    print(f"Wrote {count} records to {args.output}")


if __name__ == "__main__":
    main()
