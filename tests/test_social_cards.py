import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('social_cards', ROOT / 'scripts' / 'social_cards.py')
social_cards = importlib.util.module_from_spec(spec)
sys.modules['social_cards'] = social_cards
spec.loader.exec_module(social_cards)


class SocialCardContractTests(unittest.TestCase):
    def verified_article(self):
        return {
            'articles': [{
                'id': 'test-article',
                'section': 'ADMINISTRAȚIE',
                'headline': 'Un proiect oficial relevant pentru județ',
                'dek': 'Fapte confirmate în documentul oficial.',
                'published': '2026-08-26T06:00:00+03:00',
                'publication_mode': 'AUTO_PUBLISHED',
                'automation': {'authority': 'OWNER_APPROVED_AUTO_PUBLICATION', 'source_tier': 'T1'},
                'sources': [{'name': 'Instituție oficială', 'url': 'https://example.test/document'}],
            }]
        }

    def brief(self):
        return {
            'status': 'candidate_only',
            'product_id': 'tomorrow_locality_brief',
            'target_date': '2026-08-27',
            'localities': [{
                'uat': 'Călimănești',
                'alerts': [{
                    'valid_from': '2026-08-27T09:30:00+03:00',
                    'valid_until': '2026-08-27T14:30:00+03:00',
                    'zone': 'Circuit oficial',
                    'source_url': 'https://example.test/calendar.pdf',
                }],
            }],
        }

    def test_only_explicit_t1_publications_are_verified(self):
        payload = self.verified_article()
        unsafe = dict(payload['articles'][0])
        unsafe['id'] = 'unsafe'
        unsafe['automation'] = {'authority': 'UNAPPROVED', 'source_tier': 'T1'}
        payload['articles'].append(unsafe)
        self.assertEqual([x['id'] for x in social_cards.verified_articles(payload)], ['test-article'])

    def test_candidate_brief_never_becomes_published(self):
        cards = social_cards.candidate_cards(self.brief())
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]['state'], 'CANDIDATE_ONLY')
        self.assertIn('NU ESTE ȘTIRE PUBLICATĂ', cards[0]['state_label'])

    def test_two_formats_are_exact_and_no_post(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = social_cards.build_cards(self.verified_article(), self.brief(), directory, make_png=False)
            self.assertEqual(manifest['status'], 'CANDIDATE_NO_POST')
            self.assertFalse(manifest['auto_post'])
            self.assertEqual(len(manifest['cards']), 4)
            sizes = {(x['width'], x['height']) for x in manifest['cards']}
            self.assertEqual(sizes, {(1080, 1350), (1080, 1920)})

    def test_svg_output_is_deterministic_and_labelled(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            one = social_cards.build_cards(self.verified_article(), self.brief(), first, make_png=False)
            two = social_cards.build_cards(self.verified_article(), self.brief(), second, make_png=False)
            self.assertEqual([x['sha256'] for x in one['cards']], [x['sha256'] for x in two['cards']])
            candidate = next(x for x in one['cards'] if x['state'] == 'CANDIDATE_ONLY')
            svg = (Path(first) / candidate['svg']).read_text(encoding='utf-8')
            self.assertIn('NU ESTE ȘTIRE PUBLICATĂ', svg)
            self.assertIn('SURSĂ:', svg)

    def test_manifest_contains_provenance_without_destinations(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = social_cards.build_cards(self.verified_article(), self.brief(), directory, make_png=False)
            saved = json.loads((Path(directory) / 'manifest.json').read_text(encoding='utf-8'))
            self.assertEqual(saved, manifest)
            self.assertTrue(all(card['source_url'].startswith('https://') for card in saved['cards']))
            self.assertNotIn('destination', json.dumps(saved))


if __name__ == '__main__':
    unittest.main()
