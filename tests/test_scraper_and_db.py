import tempfile
import unittest
from pathlib import Path

from dashboard.db import DashboardDB
from scrapers.engine import scrape_source
from scrapers.eslintherok import (
    build_detail_raw_items,
    extract_candidate_sentences,
    normalize_records,
    parse_games_page,
)


class ScraperAndDbTests(unittest.TestCase):
    def test_parse_games_page_filters_noise_and_keeps_curriculum_links(self) -> None:
        html = """
        <html><body>
          <a href='/'>Home</a>
          <a href='/admin'>Admin</a>
          <a href='/textbook/our-world-1/unit-2/lesson-1'>Textbook: Our World 1 - Unit 2</a>
          <a href='/games/food'>View More</a>
          <a href='https://www.eslintherok.com/lesson/3'>Lesson 3 - Classroom Language</a>
        </body></html>
        """
        items = parse_games_page(html)
        self.assertEqual(len(items), 2)

    def test_extract_candidate_sentences_prefers_real_content(self) -> None:
        html = """
        <html><body>
            <h1>Textbook 1 Unit 2</h1>
            <p>What are you doing?</p>
            <li>I am reading a book.</li>
            <li>View More</li>
            <footer>Privacy Policy</footer>
        </body></html>
        """
        sentences = extract_candidate_sentences(html)
        self.assertIn("What are you doing?", sentences)
        self.assertIn("I am reading a book.", sentences)
        self.assertNotIn("View More", sentences)

    def test_build_detail_raw_items_expands_target_sentences(self) -> None:
        index_items = [{"url": "https://www.eslintherok.com/textbook/1/unit/2", "title": "Textbook 1 - Unit 2", "description": ""}]
        detail_pages = {
            "https://www.eslintherok.com/textbook/1/unit/2": "<p>What are you doing?</p><p>I am reading a book.</p>"
        }
        expanded = build_detail_raw_items(index_items=index_items, detail_pages=detail_pages)
        self.assertEqual(len(expanded), 2)
        self.assertTrue(any("What are you doing?" in row["title"] for row in expanded))

    def test_normalize_records_derives_textbook_unit_and_target_sentence(self) -> None:
        raw = [
            {
                "url": "https://www.eslintherok.com/textbook/our-world-1/unit/2",
                "title": "Textbook: Our World 1 - Unit 2 - What is this?",
                "description": "",
            }
        ]
        records = normalize_records(raw)
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertTrue(record.textbook)
        self.assertIn("Unit", record.textbook_unit)
        self.assertEqual(record.target_sentence, record.node_text)

    def test_db_insert_record_events_and_export_csv(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            db = DashboardDB(Path(d) / "dash.sqlite")
            run_id = db.create_run("eslintherok")
            db.add_event(run_id, "run started")

            raw = [{"url": "https://www.eslintherok.com/textbook/a/unit/1", "title": "Unit 1 - What is this?", "description": ""}]
            record = normalize_records(raw)[0]
            self.assertTrue(db.insert_record(run_id, record))
            db.increment_run_count(run_id)
            db.finish_run(run_id, "completed", "ok")

            latest = db.latest_run()
            self.assertIsNotNone(latest)
            self.assertEqual(latest["status"], "completed")
            self.assertEqual(len(db.events(run_id)), 1)
            csv_blob = db.export_csv(run_id=run_id)
            self.assertIn("target_sentence", csv_blob)
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
