import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from trust import LEGACY_STATE, VERIFIED_STATE, validate_contract, verification_state


class TrustTransparencyContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.articles = json.loads((ROOT / 'content' / 'articles.json').read_text(encoding='utf-8'))['articles']
        cls.contract = json.loads((ROOT / 'strategy' / 'trust_transparency_contract.json').read_text(encoding='utf-8'))
        cls.corrections = json.loads((ROOT / 'content' / 'corrections.json').read_text(encoding='utf-8'))
        subprocess.run([sys.executable, str(ROOT / 'scripts' / 'build.py')], check=True)

    def page(self, article_id):
        return (ROOT / '_site' / 'stiri' / article_id / 'index.html').read_text(encoding='utf-8')

    def test_contract_and_registry_validate(self):
        self.assertEqual(validate_contract(self.contract, self.corrections, {a['id'] for a in self.articles}), [])
        self.assertIsNone(self.contract['ownership_disclosure']['legal_publisher'])
        self.assertEqual(self.contract['ownership_disclosure']['status'], 'NOT_DECLARED_CANONICALLY')

    def test_current_corpus_is_one_verified_and_six_legacy(self):
        states = [verification_state(article, self.contract)['state'] for article in self.articles]
        self.assertEqual(states.count(VERIFIED_STATE), 1)
        self.assertEqual(states.count(LEGACY_STATE), 6)

    def test_every_article_exposes_visible_and_machine_readable_state(self):
        for article in self.articles:
            with self.subTest(article=article['id']):
                expected = verification_state(article, self.contract)
                page = self.page(article['id'])
                match = re.search(r'<script type="application/json" id="editorial-verification">(.+?)</script>', page)
                self.assertIsNotNone(match)
                machine_state = json.loads(match.group(1))
                self.assertEqual(machine_state, expected)
                self.assertIn(expected['label'], page)
                if expected['state'] == LEGACY_STATE:
                    self.assertNotIn('class="verification-badge verified">Publicat · verificat T1', page)
                    self.assertFalse(expected['distribution_eligible_as_verified'])

    def test_public_standards_and_corrections_are_indexable(self):
        standards = (ROOT / '_site' / 'standarde' / 'index.html').read_text(encoding='utf-8')
        corrections = (ROOT / '_site' / 'corectii' / 'index.html').read_text(encoding='utf-8')
        sitemap = (ROOT / '_site' / 'sitemap.xml').read_text(encoding='utf-8')
        self.assertIn('Cum verificăm', standards)
        self.assertIn('entității juridice', standards)
        self.assertIn('Registrul a început la', corrections)
        self.assertIn('nu dovedește că nu au existat corecții anterior', corrections)
        self.assertIn('/standarde/', sitemap)
        self.assertIn('/corectii/', sitemap)


if __name__ == '__main__':
    unittest.main()
