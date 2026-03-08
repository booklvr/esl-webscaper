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
PORT = 5000
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
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ESL Scraper Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        header {
            background: white;
            border-radius: 12px;
            padding: 30px;
            margin-bottom: 30px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        h1 { color: #333; font-size: 32px; margin-bottom: 20px; }
        .controls {
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
            align-items: center;
        }
        .control-group {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        select, input[type="number"] {
            padding: 10px 12px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 14px;
            transition: border-color 0.2s;
        }
        select:focus, input:focus { border-color: #667eea; outline: none; }
        button {
            padding: 10px 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        button:hover { transform: translateY(-2px); box-shadow: 0 6px 12px rgba(102,126,234,0.4); }
        button:active { transform: translateY(0); }
        a {
            padding: 10px 20px;
            background: white;
            color: #667eea;
            border: 2px solid #667eea;
            border-radius: 8px;
            text-decoration: none;
            font-weight: 600;
            cursor: pointer;
            font-size: 14px;
            transition: all 0.2s;
        }
        a:hover { background: #667eea; color: white; }
        
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .card {
            background: white;
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        .card h2 { font-size: 18px; color: #333; margin-bottom: 16px; font-weight: 600; }
        
        #status {
            background: #f5f5f5;
            padding: 16px;
            border-radius: 8px;
            font-family: 'Monaco', 'Courier New', monospace;
            font-size: 13px;
            color: #555;
            line-height: 1.6;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th {
            background: #f9f9f9;
            padding: 12px;
            text-align: left;
            font-weight: 600;
            font-size: 13px;
            color: #333;
            border-bottom: 2px solid #e0e0e0;
        }
        td {
            padding: 12px;
            border-bottom: 1px solid #e0e0e0;
            font-size: 13px;
            color: #666;
        }
        tr:hover td { background: #fafafa; }
        
        pre {
            background: #f5f5f5;
            padding: 12px;
            border-radius: 8px;
            overflow-y: auto;
            max-height: 300px;
            font-size: 12px;
            font-family: 'Monaco', 'Courier New', monospace;
            color: #555;
        }
        
        .status-badge {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 600;
        }
        .status-running { background: #d4edda; color: #155724; }
        .status-completed { background: #d1ecf1; color: #0c5460; }
        .status-failed { background: #f8d7da; color: #721c24; }
        
        .records-table tbody tr:hover { background: #f9f9f9; }
        code {
            background: #f4f4f4;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Monaco', monospace;
            font-size: 12px;
        }
        a.record-link {
            color: #667eea;
            padding: 0;
            background: none;
            border: none;
            cursor: pointer;
            text-decoration: underline;
        }
        a.record-link:hover { color: #764ba2; }
        
        .empty-state { color: #999; text-align: center; padding: 20px; }
    </style>
</head>
<body>
<div class="container">
    <header>
        <h1>ESL Scraper Dashboard</h1>
        <div class="controls">
            <div class="control-group">
                <label for="source">Source:</label>
                <select id="source">
                    <option value="mock">Mock (test data)</option>
                    <option value="eslintherok">ESL in the Rok (live)</option>
                </select>
            </div>
            <div class="control-group">
                <label for="limit">Limit:</label>
                <input type="number" id="limit" min="1" placeholder="optional">
            </div>
            <button id="startBtn">Start Scrape</button>
            <a href="/download.csv">Download CSV</a>
        </div>
    </header>

    <div class="grid">
        <div class="card">
            <h2>Latest Run</h2>
            <div id="status" class="empty-state">No runs yet</div>
        </div>
        <div class="card">
            <h2>Statistics</h2>
            <div id="stats" class="empty-state">No data yet</div>
        </div>
    </div>

    <div class="grid">
        <div class="card">
            <h2>Recent Runs</h2>
            <table>
                <thead>
                    <tr><th>ID</th><th>Source</th><th>Status</th><th>Records</th></tr>
                </thead>
                <tbody id="runs"></tbody>
            </table>
        </div>
        <div class="card">
            <h2>Run Events</h2>
            <pre id="events">No events yet</pre>
        </div>
    </div>

    <div class="card">
        <h2>Latest Records</h2>
        <table class="records-table">
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Type</th>
                    <th>Text</th>
                    <th>Topic</th>
                    <th>CEFR</th>
                    <th>Source</th>
                </tr>
            </thead>
            <tbody id="rows"></tbody>
        </table>
    </div>
</div>

<script>
async function refresh() {
    try {
        const statusData = await fetch('/api/status').then(r => r.json());
        const s = statusData.latest_run;
        const runEl = document.getElementById('status');
        
        if (s) {
            const statusClass = 'status-' + s.status;
            runEl.innerHTML = `
                <div style="margin-bottom: 8px;">Run <strong>#${s.id}</strong> - <span class="status-badge ${statusClass}">${s.status}</span></div>
                <div>Source: <strong>${s.source_site}</strong></div>
                <div>Records: <strong>${s.records_scraped}</strong></div>
                <div>Started: ${new Date(s.started_at_utc).toLocaleString()}</div>
                ${s.finished_at_utc ? `<div>Finished: ${new Date(s.finished_at_utc).toLocaleString()}</div>` : ''}
                ${s.message ? `<div>Message: ${s.message}</div>` : ''}
            `;
        } else {
            runEl.textContent = 'No runs yet. Start a scrape to begin!';
        }
        
        const statsEl = document.getElementById('stats');
        statsEl.innerHTML = `<div><strong>${statusData.total_records}</strong> total records</div>`;
        
        const runsData = await fetch('/api/runs?limit=10').then(r => r.json());
        const runsBody = document.getElementById('runs');
        if (runsData.runs.length === 0) {
            runsBody.innerHTML = '<tr><td colspan="4" style="text-align:center; color:#999;">No runs yet</td></tr>';
        } else {
            runsBody.innerHTML = runsData.runs.map(r => `
                <tr>
                    <td>${r.id}</td>
                    <td>${r.source_site}</td>
                    <td><span class="status-badge status-${r.status}">${r.status}</span></td>
                    <td>${r.records_scraped}</td>
                </tr>
            `).join('');
        }
        
        const recordsData = await fetch('/api/records?limit=25').then(r => r.json());
        const rowsBody = document.getElementById('rows');
        if (recordsData.records.length === 0) {
            rowsBody.innerHTML = '<tr><td colspan="6" style="text-align:center; color:#999;">No records yet</td></tr>';
        } else {
            rowsBody.innerHTML = recordsData.records.map(r => `
                <tr>
                    <td><code>${r.record_id.substring(0, 8)}</code></td>
                    <td>${r.node_type}</td>
                    <td>${r.node_text.substring(0, 50)}${r.node_text.length > 50 ? '...' : ''}</td>
                    <td>${r.topic || '-'}</td>
                    <td>${r.cefr_estimate || '-'}</td>
                    <td><a href="${r.source_url}" target="_blank" class="record-link">source</a></td>
                </tr>
            `).join('');
        }
        
        if (s) {
            const eventsData = await fetch(`/api/events?run_id=${s.id}&limit=100`).then(r => r.json());
            const eventLines = eventsData.events.reverse().map(e => {
                const time = new Date(e.created_at_utc).toLocaleTimeString();
                return `[${time}] (${e.level}) ${e.message}`;
            });
            document.getElementById('events').textContent = eventLines.length ? eventLines.join('\\n') : 'No events yet';
        } else {
            document.getElementById('events').textContent = 'No events yet';
        }
    } catch (err) {
        console.error('Refresh error:', err);
    }
}

document.getElementById('startBtn').addEventListener('click', async () => {
    const source = document.getElementById('source').value;
    const limitStr = document.getElementById('limit').value;
    const body = { source };
    if (limitStr) body.limit = Number(limitStr);
    
    try {
        const res = await fetch('/api/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        const data = await res.json();
        if (data.ok) {
            refresh();
        } else {
            alert('Error: ' + data.message);
        }
    } catch (err) {
        console.error('Start error:', err);
        alert('Failed to start scrape');
    }
});

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
