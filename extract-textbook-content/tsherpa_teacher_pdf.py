from __future__ import annotations

import argparse
import csv
import json
import os
import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urljoin
from urllib.request import Request, urlopen

DEFAULT_ARCHIVE_URL = (
    "https://cdata2.tsherpa.co.kr/ebook/tsherpa/22/22ebook_E/"
    "TB2022TC1EE_30K/resource/include/archive/index.html"
)


@dataclass(slots=True)
class ChapterPdf:
    chapter: str
    url: str


def fetch_text(url: str, timeout: float = 30.0) -> str:
    req = Request(url, headers={"User-Agent": "esl-webscraper/0.2"})
    with urlopen(req, timeout=timeout) as response:  # noqa: S310
        return response.read().decode("utf-8", errors="ignore")


def extract_teacher_pdf_links(html: str, base_url: str) -> list[ChapterPdf]:
    row_match = re.search(r"지도서\s*PDF.*?</tr>", html, flags=re.IGNORECASE | re.DOTALL)
    search_region = row_match.group(0) if row_match else html

    urls = re.findall(r"['\"]([^'\"]+\.pdf(?:\?[^'\"]*)?)['\"]", search_region, flags=re.IGNORECASE)
    seen: set[str] = set()
    results: list[ChapterPdf] = []
    for idx, raw_url in enumerate(urls, start=1):
        full_url = urljoin(base_url, raw_url)
        if full_url in seen:
            continue
        seen.add(full_url)
        results.append(ChapterPdf(chapter=infer_chapter_name(full_url, idx), url=full_url))
    return results


def infer_chapter_name(pdf_url: str, fallback_index: int) -> str:
    name = pdf_url.split("/")[-1].split("?")[0]
    lesson_match = re.search(r"(lesson\s*\d+|high\s*five\s*\d+|review\s*\d+)", name, flags=re.IGNORECASE)
    if lesson_match:
        return lesson_match.group(1).title().replace("  ", " ")
    return f"Chapter {fallback_index}"


def download_pdf(url: str, out_path: Path, timeout: float = 60.0) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    req = Request(url, headers={"User-Agent": "esl-webscraper/0.2"})
    with urlopen(req, timeout=timeout) as response:  # noqa: S310
        data = response.read()
    out_path.write_bytes(data)


def _post_json(url: str, payload: dict[str, Any], api_key: str, timeout: float = 120.0) -> dict[str, Any]:
    import urllib.error
    import urllib.request

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:  # noqa: S310
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"OpenAI API error ({exc.code}): {detail}") from exc


def upload_pdf_to_openai(pdf_path: Path, api_key: str) -> str:
    import mimetypes
    import urllib.error
    import urllib.request

    boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
    filename = pdf_path.name
    mime = mimetypes.guess_type(filename)[0] or "application/pdf"

    file_bytes = pdf_path.read_bytes()
    body = b""
    body += f"--{boundary}\r\n".encode()
    body += b'Content-Disposition: form-data; name="purpose"\r\n\r\n'
    body += b"user_data\r\n"
    body += f"--{boundary}\r\n".encode()
    body += f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode()
    body += f"Content-Type: {mime}\r\n\r\n".encode()
    body += file_bytes + b"\r\n"
    body += f"--{boundary}--\r\n".encode()

    req = urllib.request.Request(
        "https://api.openai.com/v1/files",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as response:  # noqa: S310
            parsed = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"OpenAI file upload failed ({exc.code}): {detail}") from exc
    return parsed["id"]


def extract_with_openai_file(file_id: str, chapter: str, model: str, api_key: str) -> dict[str, Any]:
    prompt = (
        "Read the attached teacher textbook PDF and extract English target language only. "
        "Return strict JSON object with keys: vocab, expressions, questions. "
        "Each key must be an array of strings. "
        f"Chapter label: {chapter}."
    )
    payload = {
        "model": model,
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_file", "file_id": file_id},
                ],
            }
        ],
        "text": {"format": {"type": "json_object"}},
    }
    response = _post_json("https://api.openai.com/v1/responses", payload, api_key)

    output_text = response.get("output_text", "").strip()
    if not output_text:
        for item in response.get("output", []):
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    output_text += content.get("text", "")
    parsed = json.loads(output_text)
    return {
        "chapter": chapter,
        "vocab": parsed.get("vocab", []),
        "expressions": parsed.get("expressions", []),
        "questions": parsed.get("questions", []),
        "source": "openai_file",
    }


def write_outputs(results: list[dict[str, Any]], out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "teacher_pdf_extraction.json"
    csv_path = out_dir / "teacher_pdf_extraction.csv"

    json_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["chapter", "type", "text"])
        writer.writeheader()
        for chapter_result in results:
            chapter = chapter_result["chapter"]
            for field in ("vocab", "expressions", "questions"):
                for text in chapter_result.get(field, []):
                    writer.writerow({"chapter": chapter, "type": field, "text": text})

    return json_path, csv_path


def run(archive_url: str, out_dir: Path, max_chapters: int | None, model: str, sleep_seconds: float) -> list[dict[str, Any]]:
    html = fetch_text(archive_url)
    pdf_links = extract_teacher_pdf_links(html, base_url=archive_url)
    if max_chapters is not None:
        pdf_links = pdf_links[:max_chapters]

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required to read PDFs with AI in this script.")

    all_results: list[dict[str, Any]] = []
    for idx, chapter_pdf in enumerate(pdf_links, start=1):
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", chapter_pdf.chapter).strip("_") or f"chapter_{idx}"
        pdf_path = out_dir / "pdfs" / f"{idx:02d}_{safe_name}.pdf"

        print(f"[{idx}/{len(pdf_links)}] Downloading {chapter_pdf.chapter}")
        download_pdf(chapter_pdf.url, pdf_path)

        print(f"[{idx}/{len(pdf_links)}] Uploading to OpenAI")
        file_id = upload_pdf_to_openai(pdf_path, api_key=api_key)

        print(f"[{idx}/{len(pdf_links)}] Extracting target language")
        extracted = extract_with_openai_file(file_id=file_id, chapter=chapter_pdf.chapter, model=model, api_key=api_key)
        extracted["pdf_url"] = chapter_pdf.url
        extracted["pdf_path"] = str(pdf_path)
        extracted["openai_file_id"] = file_id
        all_results.append(extracted)

        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    return all_results


def main() -> None:
    parser = argparse.ArgumentParser(description="Download TSherpa teacher PDFs and extract target language by chapter.")
    parser.add_argument("--archive-url", default=DEFAULT_ARCHIVE_URL)
    parser.add_argument("--out-dir", type=Path, default=Path("data/tsherpa"))
    parser.add_argument("--max-chapters", type=int, default=None)
    parser.add_argument("--model", default="gpt-4.1-mini")
    parser.add_argument("--sleep-seconds", type=float, default=0.2)
    args = parser.parse_args()

    results = run(args.archive_url, args.out_dir, args.max_chapters, args.model, args.sleep_seconds)
    json_path, csv_path = write_outputs(results, args.out_dir)
    print(f"Wrote {len(results)} chapter outputs")
    print(f"JSON: {json_path}")
    print(f"CSV:  {csv_path}")


if __name__ == "__main__":
    main()
