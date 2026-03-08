import tempfile
import unittest
from pathlib import Path

from dashboard.db import DashboardDB
from scrapers.engine import scrape_source
from scrapers.eslintherok import normalize_records, parse_games_page


class ScraperAndDbTests(unittest.TestCase):
    def test_parse_games_page_extracts_internal_links(self) -> None:
        html = """
        <html><body>
          <a href='/games/a'>Animals Game</a>
          <a href='https://www.eslintherok.com/games/b'>Food Quiz</a>
          <a href='https://example.com/skip'>Skip</a>
          <a href='/games/a'>Animals Game</a>
        </body></html>
        """
        items = parse_games_page(html)
        self.assertEqual(len(items), 2)
        self.assertTrue(items[0]["url"].startswith("https://www.eslintherok.com"))

    def test_db_insert_record_events_and_export_csv(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            db = DashboardDB(Path(d) / "dash.sqlite")
            run_id = db.create_run("eslintherok")
            db.add_event(run_id, "run started")

            raw = [{"url": "https://www.eslintherok.com/games/a", "title": "What is this?", "description": ""}]
            record = normalize_records(raw)[0]
            self.assertTrue(db.insert_record(run_id, record))
            db.increment_run_count(run_id)
            db.finish_run(run_id, "completed", "ok")

            latest = db.latest_run()
            self.assertIsNotNone(latest)
            self.assertEqual(latest["status"], "completed")
            self.assertEqual(len(db.events(run_id)), 1)
            csv_blob = db.export_csv(run_id=run_id)
            self.assertIn("node_text", csv_blob)
            self.assertIn("What is this?", csv_blob)

    def test_engine_mock_source_returns_records(self) -> None:
        events: list[str] = []
        result = scrape_source("mock", limit=3, on_event=events.append)
        self.assertEqual(result.source, "mock")
        self.assertEqual(len(result.records), 3)
        self.assertTrue(any("mock" in msg.lower() for msg in events))
        self.assertEqual(result.records[0].source_site, "mock")


if __name__ == "__main__":
    unittest.main()
