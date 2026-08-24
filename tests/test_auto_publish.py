import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

import auto_publish
import newsroom


class AutoPublishTests(unittest.TestCase):
    def test_authority_is_live_but_core_remains_locked(self):
        self.assertEqual(auto_publish.authority_errors(), [])
        cfg = auto_publish.load(ROOT / 'newsroom/publication.json')
        core = auto_publish.load(ROOT / 'newsroom/policy.json')
        self.assertTrue(cfg['auto_publish'])
        self.assertEqual(cfg['mode'], 'live')
        self.assertEqual(core['publication_mode'], 'candidate_only')
        self.assertFalse(core['auto_publish'])

    def test_fixture_safe_stories_are_eligible(self):
        _, stories, holds = newsroom.cycle(True)
        cfg = auto_publish.load(ROOT / 'newsroom/publication.json')
        self.assertEqual(len(stories), 2)
        self.assertTrue(any('REVIEW_REQUIRED_DETAIL' in h['reason'] for h in holds))
        for story in stories:
            ok, reason = auto_publish.eligible(story, cfg)
            self.assertTrue(ok, reason)

    def test_risky_candidate_cannot_promote(self):
        cfg = auto_publish.load(ROOT / 'newsroom/publication.json')
        story = {
            'status': 'DRAFT_CANDIDATE_ONLY',
            'sources': [{'name': 'ISU', 'url': 'https://example.test'}],
            'source_candidate': {
                'source_id': 'isu_valcea_comunicate',
                'tier': 'T1',
                'decision': 'READY',
                'risks': ['deced'],
            },
        }
        ok, reason = auto_publish.eligible(story, cfg)
        self.assertFalse(ok)
        self.assertEqual(reason, 'risk')

    def test_t2_cannot_promote_even_if_ready(self):
        cfg = auto_publish.load(ROOT / 'newsroom/publication.json')
        story = {
            'status': 'DRAFT_CANDIDATE_ONLY',
            'sources': [{'name': 'Local', 'url': 'https://example.test'}],
            'source_candidate': {
                'source_id': 'isu_valcea_comunicate',
                'tier': 'T2',
                'decision': 'READY',
                'risks': [],
            },
        }
        ok, reason = auto_publish.eligible(story, cfg)
        self.assertFalse(ok)
        self.assertEqual(reason, 'tier')

    def test_existing_article_is_not_republished(self):
        _, stories, _ = newsroom.cycle(True)
        cfg = auto_publish.load(ROOT / 'newsroom/publication.json')
        selected, skipped = auto_publish.select(stories, {stories[0]['id']}, cfg)
        self.assertEqual(len(selected), 1)
        self.assertTrue(any(x['reason'] == 'already_published' for x in skipped))


if __name__ == '__main__':
    unittest.main()
