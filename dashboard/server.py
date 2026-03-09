from __future__ import annotations

import argparse
import json
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from dashboard.db import DashboardDB
from scrapers.engine import UnsupportedSourceError, scrape_source

DB_PATH = Path("data/scraper_dashboard.sqlite3")
HOST = "0.0.0.0"
PORT = 8080
SUPPORTED_SOURCES = ["eslintherok", "mock"]


def launch_scrape(db: DashboardDB, source_site: str = "eslintherok", limit: int | None = None) -> None:
    run_id = db.create_run(source_site=source_site)

    def on_event(message: str) -> None:
        db.add_event(run_id=run_id, message=message, level="info")

    db.add_event(run_id=run_id, message=f"Run created for source={source_site}")

    try:
        result = scrape_source(source=source_site, limit=limit, on_event=on_event)
        inserted = 0
        for record in result.records:
            was_inserted = db.insert_record(run_id=run_id, record=record)
            if was_inserted:
                inserted += 1
                db.increment_run_count(run_id)
                if inserted % 25 == 0:
                    db.add_event(run_id=run_id, message=f"Inserted {inserted} records so far")

        db.add_event(run_id=run_id, message=f"Finished insert loop. inserted={inserted}")
        db.finish_run(run_id=run_id, status="completed", message="Scrape completed")
    except UnsupportedSourceError as exc:
        db.add_event(run_id=run_id, message=str(exc), level="error")
        db.finish_run(run_id=run_id, status="failed", message=str(exc))
    except Exception as exc:  # noqa: BLE001
        db.add_event(run_id=run_id, message=f"Unhandled error: {exc}", level="error")
        db.finish_run(run_id=run_id, status="failed", message=str(exc))


def render_dashboard() -> str:
    source_options = "".join(f'<option value="{src}">{src}</option>' for src in SUPPORTED_SOURCES)
    return f"""<!doctype html>
<html>
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>ESL Scraper Dashboard</title>
    <style>
      body {{ font-family: Arial, sans-serif; margin: 24px; }}
      .row {{ display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }}
      .card {{ border: 1px solid #ddd; border-radius: 8px; padding: 12px; margin: 12px 0; }}
      button {{ padding: 8px 14px; cursor: pointer; }}
      table {{ border-collapse: collapse; width: 100%; }}
      th, td {{ border: 1px solid #ddd; padding: 6px; font-size: 12px; text-align: left; }}
      th {{ background: #f6f6f6; }}
      code {{ background: #f4f4f4; padding: 2px 4px; }}
      .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
      pre {{ white-space: pre-wrap; max-height: 260px; overflow: auto; margin: 0; }}
    </style>
  </head>
  <body>
    <h1>ESL Scraper Dashboard</h1>
    <div class=\"row\">
      <label>Source
        <select id=\"source\">{source_options}</select>
      </label>
      <label>Limit <input id=\"limit\" type=\"number\" min=\"1\" placeholder=\"optional\" /></label>
      <button id=\"startBtn\">Start scrape</button>
      <a href=\"/download.csv\">Download all CSV</a>
    </div>

    <div class=\"card\">
      <h3>Latest run status</h3>
      <div id=\"status\">Loading...</div>
    </div>

    <div class=\"grid\">
      <div class=\"card\">
        <h3>Recent runs</h3>
        <table>
          <thead><tr><th>id</th><th>source</th><th>status</th><th>records</th></tr></thead>
          <tbody id=\"runs\"></tbody>
        </table>
      </div>
      <div class=\"card\">
        <h3>Run events (latest run)</h3>
        <pre id=\"events\">Loading...</pre>
      </div>
    </div>

    <div class=\"card\">
      <h3>Latest records</h3>
      <table>
        <thead>
          <tr>
            <th>record_id</th><th>textbook</th><th>unit</th><th>target_sentence</th><th>node_type</th><th>url</th>
          </tr>
        </thead>
        <tbody id=\"rows\"></tbody>
      </table>
    </div>

    <script>
      async function refresh() {{
        const statusData = await (await fetch('/api/status')).json();
        const s = statusData.latest_run;
        document.getElementById('status').textContent = s
          ? `Run #${{s.id}} | source=${{s.source_site}} | status=${{s.status}} | records=${{s.records_scraped}} | started=${{s.started_at_utc}} | finished=${{s.finished_at_utc || '-'}} | msg=${{s.message || '-'}} | total_records=${{statusData.total_records}}`
          : 'No runs yet.';

        const runsData = await (await fetch('/api/runs?limit=10')).json();
        document.getElementById('runs').innerHTML = runsData.runs.map(r => `
          <tr><td>${{r.id}}</td><td>${{r.source_site}}</td><td>${{r.status}}</td><td>${{r.records_scraped}}</td></tr>
        `).join('');

        const recordsData = await (await fetch('/api/records?limit=25')).json();
        document.getElementById('rows').innerHTML = recordsData.records.map(r => `
          <tr>
            <td><code>${{r.record_id}}</code></td>
            <td>${{r.textbook || ''}}</td>
            <td>${{r.textbook_unit || ''}}</td>
            <td>${{r.target_sentence || r.node_text || ''}}</td>
            <td>${{r.node_type}}</td>
            <td><a href="${{r.source_url}}" target="_blank">link</a></td>
          </tr>
        `).join('');

        if (s) {{
          const eventsData = await (await fetch(`/api/events?run_id=${{s.id}}&limit=100`)).json();
          const lines = eventsData.events.map(e => `[${{e.created_at_utc}}] (${{e.level}}) ${{e.message}}`);
          document.getElementById('events').textContent = lines.join('\n') || 'No events yet.';
        }} else {{
          document.getElementById('events').textContent = 'No events yet.';
        }}
      }}

      document.getElementById('startBtn').addEventListener('click', async () => {{
        const source = document.getElementById('source').value;
        const limit = document.getElementById('limit').value;
        const body = {{ source }};
        if (limit) body.limit = Number(limit);
        await fetch('/api/start', {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify(body) }});
        refresh();
      }});

      refresh();
      setInterval(refresh, 2000);
    </script>
  </body>
</html>
"""


class DashboardHandler(BaseHTTPRequestHandler):
    db = DashboardDB(DB_PATH)
    scrape_thread: threading.Thread | None = None

    def _json(self, payload: dict, status: int = HTTPStatus.OK) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _text(self, payload: str, content_type: str = "text/plain") -> None:
        data = payload.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/":
            self._text(render_dashboard(), content_type="text/html; charset=utf-8")
            return

        if path == "/api/status":
            self._json(
                {
                    "latest_run": self.db.latest_run(),
                    "total_records": self.db.total_records(),
                    "running": bool(self.scrape_thread and self.scrape_thread.is_alive()),
                    "sources": SUPPORTED_SOURCES,
                }
            )
            return

        if path == "/api/runs":
            qs = parse_qs(parsed.query)
            limit = int(qs.get("limit", ["20"])[0])
            self._json({"runs": self.db.runs(limit=limit)})
            return

        if path == "/api/events":
            qs = parse_qs(parsed.query)
            run_id = int(qs.get("run_id", ["0"])[0])
            limit = int(qs.get("limit", ["100"])[0])
            if run_id <= 0:
                self._json({"events": []})
                return
            self._json({"events": self.db.events(run_id=run_id, limit=limit)})
            return

        if path == "/api/records":
            qs = parse_qs(parsed.query)
            limit = int(qs.get("limit", ["50"])[0])
            offset = int(qs.get("offset", ["0"])[0])
            run_id = int(qs.get("run_id", ["0"])[0])
            self._json({"records": self.db.records(limit=limit, offset=offset, run_id=run_id or None)})
            return

        if path == "/download.csv":
            qs = parse_qs(parsed.query)
            run_id = int(qs.get("run_id", ["0"])[0])
            csv_blob = self.db.export_csv(run_id=run_id or None)
            data = csv_blob.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            filename = f"scraped_records_run_{run_id}.csv" if run_id else "scraped_records.csv"
            self.send_header("Content-Disposition", f"attachment; filename={filename}")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != "/api/start":
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return

        if self.scrape_thread and self.scrape_thread.is_alive():
            self._json({"ok": False, "message": "Scrape already running"}, status=HTTPStatus.CONFLICT)
            return

        content_len = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_len) if content_len else b"{}"

        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            self._json({"ok": False, "message": "Invalid JSON payload"}, status=HTTPStatus.BAD_REQUEST)
            return

        source = str(payload.get("source", "eslintherok"))
        limit = payload.get("limit")
        if source not in SUPPORTED_SOURCES:
            self._json(
                {"ok": False, "message": f"Unsupported source '{source}'. options={SUPPORTED_SOURCES}"},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        parsed_limit: int | None = None
        if limit is not None:
            try:
                parsed_limit = int(limit)
            except (TypeError, ValueError):
                self._json({"ok": False, "message": "limit must be an integer"}, status=HTTPStatus.BAD_REQUEST)
                return

        self.scrape_thread = threading.Thread(target=launch_scrape, args=(self.db, source, parsed_limit), daemon=True)
        self.scrape_thread.start()
        self._json({"ok": True, "message": "Scrape started", "source": source, "limit": parsed_limit})


def main() -> None:
    parser = argparse.ArgumentParser(description="Run scraper dashboard server")
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    print(f"Dashboard listening on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
