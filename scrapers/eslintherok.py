from __future__ import annotations

import argparse
import csv
import hashlib
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable, Iterable
from urllib.parse import unquote, urljoin, urlparse

from scrapers.common import PoliteHttpClient

GAMES_URL = "https://www.eslintherok.com/games"
TEXTBOOK_URL_HINTS = ("textbook", "unit", "lesson", "sentences", "dialog", "target")
NOISE_TITLES = {
    "home",
    "admin",
    "acknowledgements",
    "view more",
    "login",
    "register",
    "menu",
    "search",
    "next",
    "previous",
}
SKIP_SENTENCE_TEXT = {
    "view more",
    "click here",
    "home",
    "admin",
    "next",
    "previous",
}

EventCallback = Callable[[str], None]


@dataclass(slots=True)
class ContentRecord:
    record_id: str
    source_site: str
    source_url: str
    source_title: str
    textbook: str
    textbook_unit: str
    target_sentence: str
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


QUESTION_STARTERS = (
    "what ",
    "where ",
    "who ",
    "when ",
    "why ",
    "how ",
    "do ",
    "does ",
    "is ",
    "are ",
    "can ",
    "did ",
)


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


class SentenceExtractor(HTMLParser):
    """Collect sentence-like text from semantic content tags."""

    VALID_TAGS = {"h1", "h2", "h3", "h4", "p", "li", "td", "th", "strong", "b", "span"}

    def __init__(self) -> None:
        super().__init__()
        self.sentences: list[str] = []
        self._active_depth = 0
        self._buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in self.VALID_TAGS:
            self._active_depth += 1

    def handle_data(self, data: str) -> None:
        if self._active_depth > 0:
            self._buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() not in self.VALID_TAGS:
            return
        self._active_depth = max(0, self._active_depth - 1)
        if self._active_depth == 0 and self._buffer:
            raw = " ".join("".join(self._buffer).split())
            self._buffer = []
            if raw:
                self.sentences.append(raw)


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


def _clean_title(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" -|:")


def _is_noise_anchor(title: str, url: str) -> bool:
    title_norm = title.strip().lower()
    if not title_norm:
        return True
    if title_norm in NOISE_TITLES:
        return True
    if len(title_norm) <= 2:
        return True

    path = urlparse(url).path.lower()
    if any(part in path for part in ("/login", "/admin", "/privacy", "/terms", "/contact")):
        return True
    return False


def _looks_like_curriculum_link(title: str, url: str) -> bool:
    title_norm = title.lower()
    path_norm = urlparse(url).path.lower()

    if any(hint in path_norm for hint in TEXTBOOK_URL_HINTS):
        return True

    patterns = (
        r"\btextbook\b",
        r"\bunit\s*\d+\b",
        r"\blesson\s*\d+\b",
        r"\btarget\s+sentence",
    )
    return any(re.search(pattern, title_norm) for pattern in patterns)


def _derive_textbook_and_unit(title: str, url: str) -> tuple[str, str]:
    title_clean = _clean_title(title)
    parts = [part for part in re.split(r"\s*[|:\-–—]\s*", title_clean) if part]

    textbook = ""
    textbook_unit = ""

    for part in parts:
        if not textbook and "textbook" in part.lower():
            textbook = part
        if not textbook_unit and re.search(r"\b(unit|lesson)\b", part.lower()):
            textbook_unit = part

    decoded_path = unquote(urlparse(url).path)
    path_tokens = [token for token in re.split(r"[/_-]+", decoded_path) if token]

    if not textbook:
        for token in path_tokens:
            low = token.lower()
            if low in {"textbook", "games", "game", "lesson", "unit"}:
                continue
            if low.startswith(("unit", "lesson")):
                continue
            if token.isdigit():
                continue
            textbook = token.title()
            break

    if not textbook_unit:
        for idx, token in enumerate(path_tokens):
            low = token.lower()
            if low in {"unit", "lesson"} and idx + 1 < len(path_tokens):
                textbook_unit = f"{token.title()} {path_tokens[idx + 1]}"
                break
            if low.startswith(("unit", "lesson")):
                textbook_unit = token.title()
                break

    return _clean_title(textbook), _clean_title(textbook_unit)


def _derive_target_sentence(title: str, textbook: str, textbook_unit: str) -> str:
    candidate = _clean_title(title)
    for part in [textbook, textbook_unit]:
        if not part:
            continue
        candidate = re.sub(re.escape(part), "", candidate, flags=re.IGNORECASE).strip(" -|:")

    candidate = _clean_title(candidate)
    if not candidate:
        return _clean_title(title)
    return candidate


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
        if _is_noise_anchor(title=title, url=full_url):
            continue
        if not _looks_like_curriculum_link(title=title, url=full_url):
            continue

        seen_links.add(full_url)
        results.append({"url": full_url, "title": _clean_title(title), "description": ""})

    return results


def extract_candidate_sentences(html: str) -> list[str]:
    parser = SentenceExtractor()
    parser.feed(html)

    cleaned: list[str] = []
    seen: set[str] = set()

    for sentence in parser.sentences:
        normalized = _clean_title(sentence)
        if not normalized:
            continue
        if normalized.lower() in SKIP_SENTENCE_TEXT:
            continue
        if len(normalized.split()) < 2:
            continue
        if len(normalized) < 6:
            continue
        if len(normalized) > 140:
            continue
        if re.search(r"\b(menu|admin|copyright|privacy|terms)\b", normalized.lower()):
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(normalized)

    return cleaned


def build_detail_raw_items(index_items: Iterable[dict[str, str]], detail_pages: dict[str, str]) -> list[dict[str, str]]:
    raw_items: list[dict[str, str]] = []
    for item in index_items:
        base_title = _clean_title(item.get("title", ""))
        url = item.get("url", "").strip()
        if not base_title or not url:
            continue

        detail_html = detail_pages.get(url, "")
        sentences = extract_candidate_sentences(detail_html)
        if not sentences:
            raw_items.append({"url": url, "title": base_title, "description": ""})
            continue

        for sentence in sentences:
            raw_items.append({
                "url": url,
                "title": f"{base_title} - {sentence}",
                "description": "",
            })

    return raw_items


def normalize_records(raw_items: Iterable[dict[str, str]]) -> list[ContentRecord]:
    now = datetime.now(timezone.utc).isoformat()
    records: list[ContentRecord] = []

    for item in raw_items:
        title = _clean_title(item.get("title", ""))
        source_url = item.get("url", "").strip()
        description = item.get("description", "").strip()
        if not title or not source_url:
            continue

        textbook, textbook_unit = _derive_textbook_and_unit(title=title, url=source_url)
        target_sentence = _derive_target_sentence(title=title, textbook=textbook, textbook_unit=textbook_unit)
        node_text = target_sentence
        node_type = infer_target_type(node_text)

        records.append(
            ContentRecord(
                record_id=stable_id(source_url, title),
                source_site="eslintherok",
                source_url=source_url,
                source_title=title,
                textbook=textbook,
                textbook_unit=textbook_unit,
                target_sentence=target_sentence,
                node_text=node_text,
                node_type=node_type,
                target_type=node_type,
                activity_type="textbook_target_sentence",
                topic=textbook,
                tags="textbook;unit;target_sentence",
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


def scrape_records(client: PoliteHttpClient, limit: int | None = None, on_event: EventCallback | None = None) -> list[ContentRecord]:
    notify = on_event or (lambda _msg: None)

    index_response = client.get(GAMES_URL)
    index_items = parse_games_page(index_response.text)
    if limit is not None:
        index_items = index_items[:limit]
    notify(f"Index links after filters: {len(index_items)}")

    detail_pages: dict[str, str] = {}
    for idx, item in enumerate(index_items, start=1):
        url = item["url"]
        try:
            response = client.get(url)
            detail_pages[url] = response.text
            if idx % 10 == 0:
                notify(f"Fetched detail pages: {idx}/{len(index_items)}")
        except Exception as exc:  # noqa: BLE001
            notify(f"Detail fetch failed for {url}: {exc}")

    detail_raw_items = build_detail_raw_items(index_items=index_items, detail_pages=detail_pages)
    notify(f"Detail-derived raw items: {len(detail_raw_items)}")
    records = normalize_records(detail_raw_items)
    notify(f"Normalized content records: {len(records)}")
    return records


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
        records = scrape_records(client=client, limit=limit)
    finally:
        client.close()

    write_csv(records, output)
    return len(records)


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape ESL in the Rok into textbook/unit/target-sentence CSV")
    parser.add_argument("--output", type=Path, default=Path("data/eslintherok_games.csv"))
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    count = run(output=args.output, limit=args.limit)
    print(f"Wrote {count} records to {args.output}")


if __name__ == "__main__":
    main()
