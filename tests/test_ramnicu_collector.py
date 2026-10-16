"""Offline behavioral checks. All example administrative content is synthetic."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from administratie.ramnicu_valcea.collector import CONFIG, Fetcher, Page, ScopedRedirect, Store, collect, safe_url, run_lock
from urllib.request import Request


HOSTS = ["primariavl.ro", "dm.primariavl.ro"]
ROOT = "https://primariavl.ro/"
DOCUMENT = "https://primariavl.ro/consiliul-local/1234-exemplu-test"
BODY = b"<article><h1>EXEMPLU TEST: Hotarare Consiliul Local</h1><p>Document sintetic pentru testarea arhivei, fara valoare administrativa.</p></article>"


class FakeFetcher:
    def __init__(self, pages):
        self.pages, self.calls = pages, []

    def get(self, url):
        self.calls.append(url)
        value = self.pages[url]
        if isinstance(value, Exception):
            raise value
        return value, "text/html; charset=utf-8", url, {}


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.config = copy.deepcopy(json.loads(CONFIG.read_text(encoding="utf-8")))
        self.config.update({"max_requests": 5, "delay_seconds": 0,
                            "seeds": [{"url": ROOT, "lane": "consiliu_local", "role": "index"}]})

    def tearDown(self):
        self.tmp.cleanup()

    def test_url_scope_and_meaningful_query(self):
        url = safe_url("https://primariavl.ro/index.php?dir=PUZ%2F2026&id=495&utm_source=x#top", HOSTS)
        self.assertIn("dir=PUZ%2F2026", url)
        self.assertNotIn("utm_", url)
        for value in ["http://primariavl.ro/", "https://primariavl.ro.evil.test/", "https://user@primariavl.ro/", "https://127.0.0.1/"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                safe_url(value, HOSTS)

    def test_redirect_is_checked_before_request(self):
        with self.assertRaises(ValueError):
            ScopedRedirect(self.config).redirect_request(Request(ROOT), None, 302, "", {}, "https://outside.test/a")

    def test_navigation_does_not_become_evidence(self):
        page = Page()
        page.feed('<html><head><title>Test</title></head><nav>PUZ urbanism</nav><main><h1>Sedinta test</h1><a href="anexa.pdf">Anexa</a><p>Textul documentului de test, suficient pentru analiza.</p></main><footer>Contact</footer></html>')
        title, text, links = page.result()
        self.assertEqual(title, "Test")
        self.assertNotIn("PUZ", text)
        self.assertNotIn("Contact", text)
        self.assertEqual(links, [("anexa.pdf", "Anexa")])

    def test_empty_main_falls_back_to_visible_body_without_navigation(self):
        page = Page()
        page.feed('<html><main><div></div><nav>Navigation only</nav></main>'
                  '<div><h1>EXEMPLU TEST</h1><p>Document sintetic in afara zonei main.</p>'
                  '<a href="anexa.pdf">Anexa</a></div><footer>Contact</footer></html>')
        _, text, links = page.result()
        self.assertIn("Document sintetic", text)
        self.assertNotIn("Navigation only", text)
        self.assertNotIn("Contact", text)
        self.assertEqual(links, [("anexa.pdf", "Anexa")])

    def test_versions_and_jobs_are_idempotent_and_keep_old_evidence(self):
        store = Store(self.root)
        try:
            a = store.ingest(DOCUMENT, DOCUMENT, BODY, "text/html", "consiliu_local", "document")
            b = store.ingest(DOCUMENT, DOCUMENT, BODY, "text/html", "consiliu_local", "document")
            c = store.ingest(DOCUMENT, DOCUMENT, BODY.replace(b"sintetic", b"sintetic revizuit"), "text/html", "consiliu_local", "document")
            self.assertTrue(a["changed"])
            self.assertFalse(b["changed"])
            self.assertEqual(c["previous_sha"], a["sha"])
            self.assertEqual(store.db.execute("SELECT count(*) FROM versions").fetchone()[0], 2)
            self.assertEqual(store.export_queue(), 2)
            jobs = json.loads((self.root / "analysis_queue.json").read_text())["jobs"]
            self.assertEqual(sum(j["is_current_version"] for j in jobs), 1)
            self.assertTrue(all(not j["publication_eligible"] for j in jobs))
            for job in jobs:
                self.assertTrue((self.root / job["blob_path"]).is_file())
        finally:
            store.db.close()

    def test_one_document_can_go_to_two_specialists(self):
        store = Store(self.root)
        try:
            store.ingest(DOCUMENT, DOCUMENT, BODY.replace(b"</article>", b"<p>PUZ exemplu test urbanism</p></article>"), "text/html", "consiliu_local", "document")
            self.assertEqual({r[0] for r in store.db.execute("SELECT agent FROM jobs")}, {"consiliu_local", "urbanism"})
        finally:
            store.db.close()

    def test_unreadable_pdf_waits_for_extraction(self):
        store = Store(self.root)
        try:
            with patch("administratie.ramnicu_valcea.collector.shutil.which", return_value=None):
                result = store.ingest(DOCUMENT, DOCUMENT, b"%PDF-synthetic-test", "application/pdf", "urbanism", "document")
            self.assertEqual(result["extraction_status"], "NEEDS_PDF_EXTRACTOR")
            self.assertEqual(store.db.execute("SELECT state FROM jobs").fetchone()[0], "WAITING_EXTRACTION")
        finally:
            store.db.close()

    def test_budget_persists_frontier_and_next_run_continues(self):
        self.config["max_requests"] = 1
        fake = FakeFetcher({ROOT: ('<main><a href="' + DOCUMENT + '">Sedinta consiliul local exemplu test</a></main>').encode(), DOCUMENT: BODY})
        first = collect(self.config, self.root, fake)
        self.assertEqual(first["due_remaining"], 1)
        self.assertEqual(first["collection_status"], "DEGRADED")
        second = collect(self.config, self.root, fake)
        self.assertEqual(second["jobs_total"], 1)
        self.assertEqual(fake.calls, [ROOT, DOCUMENT])
        third = collect(self.config, self.root, fake)
        self.assertEqual(third["requests"], 0)

    def test_failure_keeps_last_success_and_never_becomes_no_news(self):
        self.config["seeds"][0].update(url=DOCUMENT, role="document")
        collect(self.config, self.root, FakeFetcher({DOCUMENT: BODY}))
        receipt = collect(self.config, self.root, FakeFetcher({DOCUMENT: RuntimeError("TEST unreachable")} ), force=True)
        self.assertEqual(receipt["collection_status"], "DEGRADED")
        store = Store(self.root)
        try:
            row = store.db.execute("SELECT * FROM documents").fetchone()
            self.assertEqual(row["status"], "BLOCKED")
            self.assertTrue(row["current_sha"])
            self.assertTrue(row["last_success"])
        finally:
            store.db.close()

    def test_robots_failure_is_cached_as_blocked(self):
        fetcher = Fetcher(self.config)
        with patch.object(fetcher, "request", side_effect=RuntimeError("TEST network blocked")) as request:
            with self.assertRaises(RuntimeError):
                fetcher.get(ROOT)
            with self.assertRaises(RuntimeError):
                fetcher.get(DOCUMENT)
            self.assertEqual(request.call_count, 1)

    def test_no_publication_mode_can_be_enabled_accidentally(self):
        self.config["publication"]["enabled"] = True
        with self.assertRaises(ValueError):
            collect(self.config, self.root, FakeFetcher({}))


    def test_pdf_replaced_by_html_waits_for_review(self):
        store = Store(self.root)
        try:
            result = store.ingest(DOCUMENT + '.pdf', DOCUMENT, BODY, 'text/html', 'urbanism', 'document')
            self.assertEqual(result['extraction_status'], 'NEEDS_REVIEW')
            self.assertEqual(store.db.execute('SELECT state FROM jobs').fetchone()[0], 'WAITING_EXTRACTION')
        finally:
            store.db.close()

    def test_second_collector_cannot_take_lock(self):
        with run_lock(self.root / 'collector.lock'):
            with self.assertRaises((OSError, BlockingIOError)):
                with run_lock(self.root / 'collector.lock'):
                    self.fail('Concurrent collector acquired the writer lock')

    def test_annex_relations_keep_parent_version(self):
        index = ('<main><h1>EXEMPLU TEST convocare sedinta</h1><a href="' + DOCUMENT + '">Consiliul local test</a></main>').encode()
        collect(self.config, self.root, FakeFetcher({ROOT: index, DOCUMENT: BODY}))
        store = Store(self.root)
        try:
            row = store.db.execute('SELECT * FROM version_links').fetchone()
            self.assertEqual(row['child_url'], DOCUMENT)
            self.assertTrue(store.db.execute('SELECT 1 FROM versions WHERE url=? AND sha=?', (ROOT, row['parent_sha'])).fetchone())
        finally:
            store.db.close()

    def test_depth_limit_is_reported_as_incomplete(self):
        self.config['max_depth'] = 0
        index = ('<main><a href="' + DOCUMENT + '">Consiliul local test</a></main>').encode()
        receipt = collect(self.config, self.root, FakeFetcher({ROOT: index}))
        self.assertEqual(receipt['collection_status'], 'DEGRADED')
        self.assertIn(DOCUMENT, receipt['depth_limited'])


if __name__ == "__main__":
    unittest.main()
