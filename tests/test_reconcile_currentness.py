import importlib.util
import hashlib
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'reconcile_civora_currentness_events.py'
spec = importlib.util.spec_from_file_location('reconcile_currentness', SCRIPT)
reconcile = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reconcile)


class ReconcileCurrentnessTests(unittest.TestCase):
    def run_projection(self, active):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = {name: root / (name + '.json') for name in ('ARTICLES', 'EVENTS', 'LOCAL_LIFE', 'STATE')}
            paths['ARTICLES'].write_text(json.dumps({'articles': [{'id': 'durable', 'title': 'Preserved archive', 'published': '2026-09-01T12:00:00+03:00'}]}), encoding='utf-8')
            paths['LOCAL_LIFE'].write_text(json.dumps({'restaurants': [{'id': 'keep'}]}), encoding='utf-8')
            paths['STATE'].write_text(json.dumps({'lead_story_id': 'stale-lead', 'lead_published_at': '2026-08-01T12:00:00+03:00', 'articles_sha256': 'stale-hash'}), encoding='utf-8')
            manifest = {'stories': [{'id': 'durable', 'public_ux_authorized': True, 'structured_data_type': 'NewsArticle', 'active_now': active, 'archive_status': 'active' if active else 'published_archive'}]}
            with patch.multiple(reconcile, **paths):
                result = reconcile.apply(manifest, {'events': []}, {}, datetime(2026, 10, 9, 6, tzinfo=reconcile.TZ))
            docs = {name: json.loads(path.read_text(encoding='utf-8')) for name, path in paths.items()}
            docs['ARTICLE_BYTES_SHA256'] = hashlib.sha256(paths['ARTICLES'].read_bytes()).hexdigest()
            return result, docs

    def test_zero_current_persists_archive_and_clears_stale_lead(self):
        report, docs = self.run_projection(False)
        self.assertEqual(report['current'], [])
        self.assertEqual(docs['ARTICLES']['current_story_ids'], [])
        self.assertEqual(docs['ARTICLES']['archive_story_ids'], ['durable'])
        self.assertEqual(docs['ARTICLES']['articles'][0]['title'], 'Preserved archive')
        self.assertTrue(docs['ARTICLES']['articles'][0]['archive_only'])
        self.assertEqual(docs['STATE']['current_story_count'], 0)
        self.assertEqual(docs['STATE']['archive_story_count'], 1)
        self.assertIsNone(docs['STATE']['lead_story_id'])
        self.assertIsNone(docs['STATE']['lead_published_at'])
        self.assertEqual(docs['LOCAL_LIFE']['restaurants'], [{'id': 'keep'}])

    def test_nonempty_current_still_sets_lead(self):
        report, docs = self.run_projection(True)
        self.assertEqual(report['current'], ['durable'])
        self.assertEqual(docs['STATE']['lead_story_id'], 'durable')
        self.assertEqual(docs['STATE']['lead_published_at'], docs['ARTICLES']['articles'][0]['published'])
        self.assertEqual(docs['STATE']['archive_story_count'], 0)

    def test_receipt_hash_matches_reconciled_file_for_both_currentness_states(self):
        for active in (True, False):
            with self.subTest(active=active):
                _, docs = self.run_projection(active)
                self.assertEqual(docs['STATE']['articles_sha256'], docs['ARTICLE_BYTES_SHA256'])

    def test_missing_archive_still_refuses_projection(self):
        manifest = {'stories': [{'id': 'missing', 'public_ux_authorized': True, 'structured_data_type': 'NewsArticle', 'active_now': False}]}
        with self.assertRaises(SystemExit):
            reconcile.reconcile_articles({'articles': []}, manifest)
