from __future__ import annotations

import csv
import io
import sqlite3
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from scrapers.eslintherok import ContentRecord


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS scrape_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_site TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at_utc TEXT NOT NULL,
    finished_at_utc TEXT,
    message TEXT,
    records_scraped INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS scraped_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    record_id TEXT NOT NULL,
    source_site TEXT NOT NULL,
    source_url TEXT NOT NULL,
    source_title TEXT NOT NULL,
    node_text TEXT NOT NULL,
    node_type TEXT NOT NULL,
    target_type TEXT NOT NULL,
    activity_type TEXT,
    topic TEXT,
    tags TEXT,
    description TEXT,
    grade_level TEXT,
    esl_level TEXT,
    language TEXT,
    cefr_estimate TEXT,
    difficulty_score TEXT,
    complexity_score TEXT,
    grammar_patterns TEXT,
    source_author TEXT,
    source_license TEXT,
    content_hash TEXT,
    scraped_at_utc TEXT,
    created_at_utc TEXT NOT NULL,
    UNIQUE(record_id),
    FOREIGN KEY(run_id) REFERENCES scrape_runs(id)
);

CREATE TABLE IF NOT EXISTS scrape_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    created_at_utc TEXT NOT NULL,
    level TEXT NOT NULL,
    message TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES scrape_runs(id)
);
"""


class DashboardDB:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA_SQL)

    def create_run(self, source_site: str) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO scrape_runs (source_site, status, started_at_utc)
                VALUES (?, 'running', ?)
                """,
                (source_site, now),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def add_event(self, run_id: int, message: str, level: str = "info") -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO scrape_events (run_id, created_at_utc, level, message) VALUES (?, ?, ?, ?)",
                (run_id, now, level, message),
            )
            conn.commit()

    def events(self, run_id: int, limit: int = 200) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM scrape_events
                WHERE run_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (run_id, limit),
            ).fetchall()
            return [dict(row) for row in rows]

    def finish_run(self, run_id: int, status: str, message: str = "") -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE scrape_runs
                SET status = ?, finished_at_utc = ?, message = ?
                WHERE id = ?
                """,
                (status, now, message, run_id),
            )
            conn.commit()

    def increment_run_count(self, run_id: int, amount: int = 1) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE scrape_runs SET records_scraped = records_scraped + ? WHERE id = ?",
                (amount, run_id),
            )
            conn.commit()

    def insert_record(self, run_id: int, record: ContentRecord) -> bool:
        payload = asdict(record)
        payload["run_id"] = run_id
        payload["created_at_utc"] = datetime.now(timezone.utc).isoformat()
        columns = list(payload.keys())
        placeholders = ",".join(["?" for _ in columns])

        with self._connect() as conn:
            try:
                conn.execute(
                    f"INSERT INTO scraped_records ({','.join(columns)}) VALUES ({placeholders})",
                    tuple(payload[col] for col in columns),
                )
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def latest_run(self) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM scrape_runs ORDER BY id DESC LIMIT 1").fetchone()
            return dict(row) if row else None

    def runs(self, limit: int = 20) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM scrape_runs ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]

    def records(self, limit: int = 100, offset: int = 0, run_id: int | None = None) -> list[dict]:
        sql = "SELECT * FROM scraped_records"
        params: list[int] = []
        if run_id is not None:
            sql += " WHERE run_id = ?"
            params.append(run_id)
        sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self._connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
            return [dict(row) for row in rows]

    def total_records(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS c FROM scraped_records").fetchone()
            return int(row["c"])

    def export_csv(self, run_id: int | None = None) -> str:
        rows = self.records(limit=max(self.total_records(), 1), offset=0, run_id=run_id)
        if not rows:
            return ""
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
        return output.getvalue()
