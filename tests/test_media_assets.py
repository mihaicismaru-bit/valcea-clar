import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import media_assets as media


class VerifiedBuildReuseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.previous = self.root / 'previous'
        self.article = {
            'image': 'verified.jpg', 'image_fetch_url': 'https://example.com/photo.jpg',
            'image_origin_url': 'https://example.com/photo.jpg',
            'image_source_url': 'https://example.com/source', 'image_credit': 'Credit',
            'image_rights_basis': 'licensed', 'image_license_url': 'https://example.com/license',
            'image_provenance_status': 'VERIFIED',
        }
        self.data = b'\xff\xd8\xffphoto-test-bytes'
        self.manifest = patch.object(media, '_local_manifest', return_value={})
        self.manifest.start()
        self.addCleanup(self.manifest.stop)
        with patch.object(media, '_download_image', return_value=(self.data, self.article['image_fetch_url'])):
            media.materialize_media(self.previous, [self.article])

    def test_second_build_reuses_exact_verified_bytes_without_network(self):
        target = self.root / 'next'
        with patch.object(media, '_download_image', side_effect=RuntimeError('HTTP 429')) as download:
            result = media.materialize_media(target, [self.article], previous_media_dir=self.previous)
        download.assert_not_called()
        self.assertEqual(result, {'verified.jpg'})
        self.assertEqual((target / 'verified.jpg').read_bytes(), self.data)
        before = json.loads((self.previous / 'provenance.json').read_text())
        after = json.loads((target / 'provenance.json').read_text())
        self.assertEqual(before, after)

    def test_changed_rights_or_origin_cannot_reuse_previous_bytes(self):
        for key in ('image_origin_url', 'image_fetch_url', 'image_credit', 'image_rights_basis', 'image_license_url'):
            with self.subTest(key=key), patch.object(media, '_download_image', side_effect=RuntimeError('HTTP 429')) as download:
                target = self.root / key
                changed = {**self.article, key: 'https://example.com/changed'}
                result = media.materialize_media(target, [changed], previous_media_dir=self.previous)
                self.assertNotIn('verified.jpg', result)
                self.assertTrue(download.called)
                self.assertTrue(json.loads((target / 'provenance.json').read_text())['mirror_failures'])

    def test_corrupt_bytes_are_rejected_and_fetched_again(self):
        (self.previous / 'verified.jpg').write_bytes(b'\xff\xd8\xffcorrupt')
        with patch.object(media, '_download_image', return_value=(self.data, self.article['image_fetch_url'])) as download:
            target = self.root / 'recovered'
            media.materialize_media(target, [self.article], previous_media_dir=self.previous)
        self.assertTrue(download.called)
        self.assertEqual((target / 'verified.jpg').read_bytes(), self.data)

    def test_removed_or_unverified_media_is_not_carried_into_next_build(self):
        for rows in ([], [{**self.article, 'image_provenance_status': 'HOLD'}]):
            with self.subTest(rows=rows), patch.object(media, '_download_image') as download:
                target = self.root / str(len(rows))
                result = media.materialize_media(target, rows, previous_media_dir=self.previous)
                self.assertNotIn('verified.jpg', result)
                self.assertFalse((target / 'verified.jpg').exists())
                download.assert_not_called()
