"""Windows runtime evidence integrity and PDF extraction tests; synthetic fixtures only."""
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import subprocess
from types import SimpleNamespace
import xml.etree.ElementTree as ET
import unittest
from unittest.mock import patch
import zipfile

from administratie.ramnicu_valcea.windows_install import NS, TASK_NAME, install, task_xml
from administratie.ramnicu_valcea.collector import CONFIG, Store
from administratie.ramnicu_valcea.windows_runtime import backup_evidence, restore_evidence, run, status, verify_backup


URL = "https://primariavl.ro/consiliul-local/1234-test"
BODY = b"<article><h1>EXEMPLU TEST consiliul local</h1><p>Continut sintetic pentru verificarea colectarii si restaurarii arhivei.</p></article>"


class FakeFetcher:
    def get(self, url):
        return BODY, "text/html", url, {}


def synthetic_pdf():
    text = b"BT /F1 12 Tf 72 720 Td (EXEMPLU TEST: document sintetic de consiliu pentru verificarea extragerii PDF.) Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(text)).encode() + b" >>\nstream\n" + text + b"\nendstream",
    ]
    data, offsets = b"%PDF-1.4\n", [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(data))
        data += str(index).encode() + b" 0 obj\n" + obj + b"\nendobj\n"
    xref = len(data)
    data += b"xref\n0 6\n0000000000 65535 f \n"
    data += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:])
    return data + b"trailer\n<< /Root 1 0 R /Size 6 >>\nstartxref\n" + str(xref).encode() + b"\n%%EOF\n"


class WindowsRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.config = copy.deepcopy(json.loads(CONFIG.read_text(encoding="utf-8")))
        self.config.update(seeds=[{"url": URL, "lane": "consiliu_local", "role": "document"}],
                           delay_seconds=0, max_requests=1)

    def tearDown(self):
        self.tmp.cleanup()

    def test_run_produces_restorable_backup_and_idempotent_queue(self):
        first = run(self.root, self.config, fetcher=FakeFetcher())
        self.assertEqual(first["health"], "BOUNDED_SCAN_COMPLETE")
        self.assertEqual(first["published"], 0)
        self.assertEqual(first["pilot_status"], "INCOMPLETE_COVERAGE")
        self.assertTrue(first["backup"]["verified"])
        restored = self.root / "restored"
        self.assertTrue(restore_evidence(first["backup"]["path"], restored)["verified"])
        db = Store(restored)
        try:
            self.assertEqual(db.db.execute("SELECT count(*) FROM versions").fetchone()[0], 1)
            sha = hashlib.sha256(BODY).hexdigest()
            self.assertEqual((restored / "blobs" / sha[:2] / sha).read_bytes(), BODY)
        finally:
            db.db.close()
        second = run(self.root, self.config, fetcher=FakeFetcher())
        self.assertEqual(second["requests"], 0)
        self.assertEqual(second["jobs"], 1)
        self.assertEqual(status(self.root)["publication"], "DISABLED")

    def test_tampered_backup_is_rejected_before_restore_writes(self):
        result = run(self.root, self.config, fetcher=FakeFetcher())
        damaged = self.root / "damaged.zip"
        with zipfile.ZipFile(result["backup"]["path"]) as source, zipfile.ZipFile(damaged, "w") as target:
            for name in source.namelist():
                target.writestr(name, b"tampered" if name == "evidence.sqlite" else source.read(name))
        restored = self.root / "must-not-exist"
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            restore_evidence(damaged, restored)
        self.assertFalse(restored.exists())

    def test_backup_path_traversal_is_rejected(self):
        archive = self.root / "unsafe.zip"
        body = b"outside"
        manifest = {"schema_version": 1, "members": {"../outside": {
            "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}}}
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr("../outside", body)
            z.writestr("manifest.json", json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "Unsafe backup member"):
            verify_backup(archive)

    def test_restore_never_overwrites_existing_directory(self):
        result = run(self.root, self.config, fetcher=FakeFetcher())
        existing = self.root / "existing"
        existing.mkdir()
        marker = existing / "keep.txt"
        marker.write_text("keep")
        with self.assertRaises(FileExistsError):
            restore_evidence(result["backup"]["path"], existing)
        self.assertEqual(marker.read_text(), "keep")

    def test_unhandled_failure_is_recorded_and_never_healthy(self):
        with patch("administratie.ramnicu_valcea.windows_runtime.collect", side_effect=RuntimeError("TEST runner error")):
            result = run(self.root, self.config)
        self.assertEqual(result["health"], "FAILED")
        self.assertIn("TEST runner error", result["error"])
        self.assertEqual(status(self.root)["health"], "FAILED")

    def test_status_marks_an_old_heartbeat_stale(self):
        run(self.root, self.config, fetcher=FakeFetcher())
        path = self.root / "runtime" / "windows" / "status.json"
        record = json.loads(path.read_text())
        record["finished_at"] = (datetime.now(timezone.utc) - timedelta(hours=31)).isoformat()
        path.write_text(json.dumps(record))
        self.assertEqual(status(self.root)["health"], "STALE")

    def test_backup_retention_keeps_last_seven_verified_archives(self):
        run(self.root, self.config, fetcher=FakeFetcher())
        for _ in range(7):
            backup_evidence(self.root / "runtime" / "ramnicu", self.root / "runtime" / "backups")
        archives = list((self.root / "runtime" / "backups").glob("ramnicu-*.zip"))
        self.assertEqual(len(archives), 7)
        for archive in archives:
            verify_backup(archive)

    def test_task_definition_uses_current_user_and_recovers_missed_runs(self):
        xml = ET.fromstring(task_xml(self.root, self.root / "pythonw.exe", "TEST\\user", "07:15"))
        self.assertEqual(xml.findtext(".//{" + NS + "}UserId"), "TEST\\user")
        self.assertEqual(xml.findtext(".//{" + NS + "}LogonType"), "InteractiveToken")
        self.assertEqual(xml.findtext(".//{" + NS + "}StartWhenAvailable"), "true")
        self.assertEqual(xml.findtext(".//{" + NS + "}MultipleInstancesPolicy"), "IgnoreNew")
        self.assertEqual(xml.findtext(".//{" + NS + "}ExecutionTimeLimit"), "PT1H")
        self.assertIn('"' + str(self.root) + '"', xml.findtext(".//{" + NS + "}Arguments"))

    def test_failed_task_registration_is_recorded(self):
        exe = self.root / ".venv" / "Scripts" / "pythonw.exe"
        exe.parent.mkdir(parents=True)
        exe.touch()
        responses = [subprocess.CompletedProcess([], 0, "TEST\\user", ""),
                     subprocess.CompletedProcess([], 1, "", "TEST not found"),
                     subprocess.CompletedProcess([], 1, "", "TEST Scheduler unavailable")]
        with patch("administratie.ramnicu_valcea.windows_install.os", SimpleNamespace(name="nt")), \
             patch("administratie.ramnicu_valcea.windows_install.subprocess.run", side_effect=responses):
            result = install(self.root)
        self.assertEqual(result["status"], "INSTALL_FAILED")
        self.assertFalse(result["registered"])
        self.assertIn("TEST Scheduler unavailable", result["error"])

    def test_installer_never_overwrites_an_unmanaged_task(self):
        exe = self.root / ".venv" / "Scripts" / "pythonw.exe"
        exe.parent.mkdir(parents=True)
        exe.touch()
        existing = '<Task xmlns="' + NS + '"><RegistrationInfo><Author>Other</Author></RegistrationInfo></Task>'
        responses = [subprocess.CompletedProcess([], 0, "TEST\\user", ""),
                     subprocess.CompletedProcess([], 0, existing, "")]
        with patch("administratie.ramnicu_valcea.windows_install.os", SimpleNamespace(name="nt")), \
             patch("administratie.ramnicu_valcea.windows_install.subprocess.run", side_effect=responses) as command:
            result = install(self.root)
        self.assertEqual(result["status"], "INSTALL_FAILED")
        self.assertIn("unmanaged", result["error"])
        self.assertEqual(command.call_count, 2)

    @unittest.skipUnless(importlib.util.find_spec("pypdf"), "pypdf not installed")
    def test_pdf_fallback_extracts_real_text_in_subprocess(self):
        db = Store(self.root / "data")
        try:
            with patch("administratie.ramnicu_valcea.collector.shutil.which", return_value=None):
                result = db.ingest(URL + ".pdf", URL + ".pdf", synthetic_pdf(),
                                   "application/pdf", "consiliu_local", "document")
            self.assertEqual(result["extraction_status"], "EXTRACTED")
            self.assertEqual(db.db.execute("SELECT state FROM jobs").fetchone()[0], "READY")
            self.assertIn("EXEMPLU TEST", (db.root / "text" / (result["sha"] + ".txt")).read_text())
        finally:
            db.db.close()


if __name__ == "__main__":
    unittest.main()
