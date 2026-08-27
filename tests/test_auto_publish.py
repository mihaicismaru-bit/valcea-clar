import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

import auto_publish


class StandalonePublisherRevocationTests(unittest.TestCase):
    def test_parallel_publisher_is_revoked(self):
        cfg = auto_publish.load(ROOT / 'newsroom/publication.json')
        self.assertFalse(cfg['auto_publish'])
        self.assertEqual(cfg['mode'], 'deprecated_parallel_newsroom')
        self.assertEqual(cfg['allowed_tiers'], [])
        self.assertEqual(cfg['allowed_source_ids'], [])
        self.assertEqual(cfg['max_per_cycle'], 0)
        self.assertEqual(cfg['canonical_editorial_engine'], 'mihaicismaru-bit/civora')

    def test_legacy_publisher_fails_closed(self):
        errors = auto_publish.authority_errors()
        self.assertTrue(errors)
        self.assertIn('auto-publication authority is not live', errors)


if __name__ == '__main__':
    unittest.main()
