"""F0 historical release dry-run using the REAL, unchanged public reconciler.

Offline, hermetic: imports scripts/reconcile_civora_currentness_events.py and
copies the already-published public JSON into a temporary directory. Pins:
CIVORA eb3b4de9, public f7a82a2. Never fetches URLs, modifies production,
dispatches workflows, or treats a green test as a delivery receipt.

Only editorial-authorized historical manifest rows are included in the fixture.
Expiry/zero-current variants are synthetic test branches, NOT new approvals.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "tests/fixtures/f0_pinned_civora_20261011.json"
SCRIPT_PATH = ROOT / "scripts/reconcile_civora_currentness_events.py"

spec = importlib.util.spec_from_file_location("f0_real_public_reconciler", SCRIPT_PATH)
reconcile = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(reconcile)

FIXTURE = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
NOW = datetime(2026, 10, 11, 18, 43, 31, tzinfo=reconcile.TZ)
SERVICE_ID = "valcea-intrerupere-curent-2026-10-11-horezu"
PUBLIC_FILES = {
    "ARTICLES": "content/articles.json",
    "EVENTS": "content/events.json",
    "LOCAL_LIFE": "content/local_life.json",
    "STATE": "sync/civora_state.json",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def blob_sha(path: Path) -> str:
    return subprocess.check_output(
        ["git", "hash-object", str(path)],
        cwd=ROOT, text=True
    ).strip()


def ids_and_titles(doc: dict) -> dict[str, str]:
    return {str(row["id"]): str(row.get("headline") or "") for row in doc["articles"]}


class F0PinnedReconcilerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pins = FIXTURE["public_pin"]
        cls.source = {key: ROOT / value for key, value in PUBLIC_FILES.items()}
        for path in cls.source.values():
            if not path.is_file():
                raise AssertionError("Missing pinned public input " + str(path))
        expected_blobs = {
            SCRIPT_PATH: pins["reconciler_blob_sha"],
            cls.source["ARTICLES"]: pins["articles_blob_sha"],
            cls.source["EVENTS"]: pins["events_blob_sha"],
            cls.source["LOCAL_LIFE"]: pins["local_life_blob_sha"],
            cls.source["STATE"]: pins["state_blob_sha"],
        }
        for path, expected in expected_blobs.items():
            actual = blob_sha(path)
            if actual != expected:
                raise AssertionError(f"F0_PIN_DRIFT:{path.relative_to(ROOT)} {actual} != {expected}")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="valcea_f0_pinned_offline_")
        root = Path(self.tmp.name)
        self.paths = {key: root / (key.lower() + ".json") for key in PUBLIC_FILES}
        for key, path in self.paths.items():
            shutil.copy2(self.source[key], path)
        self.original_article_doc = json.loads(self.source["ARTICLES"].read_text(encoding="utf-8"))
        self.original_state = json.loads(self.source["STATE"].read_text(encoding="utf-8"))

    def tearDown(self):
        self.tmp.cleanup()

    def execute(self, manifest: dict | None = None, now: datetime = NOW) -> dict:
        with patch.multiple(reconcile, **self.paths):
            report = reconcile.apply(
                copy.deepcopy(manifest if manifest is not None else FIXTURE["manifest"]),
                copy.deepcopy(FIXTURE["canonical_events"]),
                copy.deepcopy(FIXTURE["canonical_surfaces"]),
                now,
            )
        return report

    def read(self, key: str) -> dict:
        return json.loads(self.paths[key].read_text(encoding="utf-8"))

    def check_receipt(self, current: int, archived: int) -> None:
        rows = self.read("ARTICLES")
        state = self.read("STATE")
        self.assertEqual(len(rows["articles"]), 100)
        self.assertEqual(len(set(ids_and_titles(rows))), 100)
        self.assertEqual(state["current_story_count"], current)
        self.assertEqual(state["archive_story_count"], archived)
        self.assertEqual(state["articles_sha256"], sha256(self.paths["ARTICLES"]))
        self.assertEqual(len(rows["current_story_ids"]), current)
        self.assertEqual(len(rows["archive_story_ids"]), archived)
        self.assertEqual(ids_and_titles(rows), ids_and_titles(self.original_article_doc))
        self.assertEqual(state.get("synced_at"), self.original_state.get("synced_at"))
        self.assertEqual(state.get("source_generated_at"), self.original_state.get("source_generated_at"))
        self.assertEqual(state.get("ownership"), self.original_state.get("ownership"))

    def test_01_exact_pins_100_story_archive(self):
        self.assertEqual(FIXTURE["source_pin"]["commit"], "eb3b4de9fc6eda0af94b11ad5acecbb4ba4ff7e0")
        self.assertEqual(FIXTURE["public_pin"]["commit"], "f7a82a245e2dcec5b957f37ca26dc3038dba95d0")
        man = FIXTURE["manifest"]["stories"]
        pub = self.original_article_doc["articles"]
        self.assertEqual(len(man), 100)
        self.assertEqual(len(pub), 100)
        self.assertEqual({row["id"] for row in man}, {row["id"] for row in pub})
        self.assertEqual(sum(row["active_now"] is True for row in man), 9)
        self.assertEqual(len(self.original_article_doc["archive_story_ids"]), 91)
        self.assertEqual(len(FIXTURE["canonical_events"]["events"]), 36)
        self.assertIn(SERVICE_ID, {row["id"] for row in man})

    def test_02_changed_false_does_not_invent_release_event(self):
        d = FIXTURE["decision"]
        st = FIXTURE["newsroom_state"]
        ev = FIXTURE["publication_event"]
        self.assertIs(d["changed"], False)
        self.assertEqual(d["new_story_ids"], [])
        self.assertEqual(d["fingerprint"], st["last_published_fingerprint"])
        self.assertEqual(ev["fingerprint"], st["last_published_fingerprint"])
        self.assertEqual(d["publishable_story_ids"], st["last_published_story_ids"])
        self.assertEqual(ev["story_ids"], st["last_published_story_ids"])
        self.assertEqual(ev["published_at"], st["last_published_at"])
        self.assertLess(datetime.fromisoformat(ev["published_at"]), datetime.fromisoformat(d["evaluated_local"]))
        self.assertEqual(len(ev["new_story_ids"]), 1)
        # The PUBLIC reconciler does not own/write any of these CIVORA ledger files.
        self.execute()
        self.check_receipt(9, 91)
        self.assertEqual(self.read("STATE").get("source_generated_at"), self.original_state.get("source_generated_at"))

    def test_03_pinned_live_100_preserved_and_receipt_exact(self):
        rep = self.execute()
        self.assertEqual(len(rep["current"]), 9)
        self.assertEqual(rep["archive_count"], 91)
        self.check_receipt(9, 91)
        self.assertEqual(self.read("STATE")["lead_story_id"], self.read("ARTICLES")["current_story_ids"][0])
        # Existing local directory is the only writable destination.
        self.assertEqual(blob_sha(self.source["ARTICLES"]), FIXTURE["public_pin"]["articles_blob_sha"])

    def test_04_authorized_zero_current_100_routes_retained(self):
        manifest = copy.deepcopy(FIXTURE["manifest"])
        for row in manifest["stories"]:
            row["active_now"] = False
            row["archive_status"] = "published_archive"
        result = self.execute(manifest)
        self.assertEqual(result["current"], [])
        self.assertEqual(result["archive_count"], 100)
        self.check_receipt(0, 100)
        self.assertEqual(self.read("STATE")["lead_story_id"], None)
        self.assertEqual(self.read("STATE")["lead_published_at"], None)
        first_bytes = {k: p.read_bytes() for k, p in self.paths.items()}
        self.execute(manifest)
        second_bytes = {k: p.read_bytes() for k, p in self.paths.items()}
        self.assertEqual(first_bytes, second_bytes, "Fixed-clock repeated reconcile must be byte-idempotent")

    def test_05_expired_horezu_remains_current_without_upstream_demote(self):
        self.execute()
        # RISK REPRODUCED, not successful expiry handling: real public code
        # trusts upstream active_now and ignores the expired 09:00-14:00 window.
        self.assertIn(SERVICE_ID, self.read("ARTICLES")["current_story_ids"])
        manifest = copy.deepcopy(FIXTURE["manifest"])
        for row in manifest["stories"]:
            if row["id"] == SERVICE_ID:
                row["active_now"] = False
                row["archive_status"] = "published_archive"
        self.execute(manifest)
        self.check_receipt(8, 92)
        self.assertNotIn(SERVICE_ID, self.read("ARTICLES")["current_story_ids"])
        self.assertIn(SERVICE_ID, self.read("ARTICLES")["archive_story_ids"])

    def test_06_clock_only_churn_is_not_editorial_delivery(self):
        self.execute(now=NOW)
        before_articles = self.paths["ARTICLES"].read_bytes()
        before_events = self.read("EVENTS")
        before_local_life = self.read("LOCAL_LIFE")
        before_state = self.read("STATE")
        self.execute(now=NOW + timedelta(seconds=10))
        after_state = self.read("STATE")
        self.assertEqual(self.paths["ARTICLES"].read_bytes(), before_articles)
        self.assertEqual(after_state["articles_sha256"], before_state["articles_sha256"])
        self.assertNotEqual(before_events["updated_at"], self.read("EVENTS")["updated_at"])
        self.assertNotEqual(before_local_life["updated_at"], self.read("LOCAL_LIFE")["updated_at"])
        self.assertNotEqual(before_state["local_life_surface_updated_at"], after_state["local_life_surface_updated_at"])
        # Expected debt P2: public files churn by execution clock without
        # an editorial publication event. No site-delivered claim is made.

    def test_07_original_self_test_not_regressed(self):
        self.assertEqual(reconcile.self_test(), 0)


if __name__ == "__main__":
    unittest.main()
