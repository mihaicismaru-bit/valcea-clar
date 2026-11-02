import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from scripts.publish_from_evidence import prepare


class EvidencePublicationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = 'https://primariavl.ro/test/123-document'
        blob = b'<html><body>Primaria anunta un program pentru cetateni incepand de luni.</body></html>'
        self.sha = hashlib.sha256(blob).hexdigest()
        (self.root / 'blob').write_bytes(blob)
        (self.root / 'text').write_text('Primaria anunta un program pentru cetateni incepand de luni.', encoding='utf-8')
        db = sqlite3.connect(self.root / 'evidence.sqlite')
        try:
            db.execute('CREATE TABLE versions (url TEXT, sha TEXT, blob_path TEXT, text_path TEXT, content_type TEXT, extraction_status TEXT)')
            db.execute('INSERT INTO versions VALUES (?,?,?,?,?,?)', (self.source, self.sha, 'blob', 'text', 'text/html', 'EXTRACTED'))
            db.commit()
        finally:
            db.close()
        self.proj = self.root / 'articles.json'
        self.proj.write_text(json.dumps({'articles': [{'id': 'other'}], 'current_story_ids': ['other']}), encoding='utf-8')
        self.review = self.root / 'review.json'
        self.item = {'id': 'test-article', 'source_url': self.source, 'source_sha256': self.sha,
                     'editorially_verified': True, 'section': 'UTIL', 'headline': 'Program', 'dek': 'Program nou',
                     'published': '2026-11-02T09:00:00+02:00', 'paragraphs': [
                         {'text': 'Primăria a anunțat programul.', 'source_excerpt': 'Primaria anunta un program pentru cetateni'}]}
        self.write_review()
        self.out = self.root / 'output.json'

    def write_review(self):
        self.review.write_text(json.dumps(self.item), encoding='utf-8')

    def run_prepare(self):
        return prepare(self.root, self.proj, self.review, self.out)

    def test_preserves_prior_content_and_deduplicates(self):
        self.assertEqual(self.run_prepare(), 'prepared')
        doc = json.loads(self.out.read_text(encoding='utf-8'))
        self.assertEqual([a['id'] for a in doc['articles']], ['test-article', 'other'])
        self.assertEqual(doc['current_story_ids'], ['test-article', 'other'])
        self.assertEqual(prepare(self.root, self.out, self.review, self.root / 'next.json'), 'already-present')
        self.item['id'] = 'another-article'
        self.write_review()
        with self.assertRaises(ValueError):
            prepare(self.root, self.out, self.review, self.root / 'next.json')

    def test_missing_evidence_or_unreviewed_article_fails(self):
        self.item['paragraphs'][0]['source_excerpt'] = 'afirmatie care nu exista in document'
        self.write_review()
        with self.assertRaises(ValueError): self.run_prepare()
        self.item['editorially_verified'] = False
        self.write_review()
        with self.assertRaises(ValueError): self.run_prepare()
        self.assertFalse(self.out.exists())

    def test_changed_blob_and_active_wal_fail(self):
        (self.root / 'blob').write_bytes(b'tampered')
        with self.assertRaises(ValueError): self.run_prepare()
        (self.root / 'evidence.sqlite-wal').write_bytes(b'uncheckpointed')
        with self.assertRaises(ValueError): self.run_prepare()
        self.assertFalse(self.out.exists())


if __name__ == '__main__':
    unittest.main()
