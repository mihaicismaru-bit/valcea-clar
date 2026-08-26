import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SiteUXContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run([sys.executable, str(ROOT / 'scripts' / 'build.py')], check=True)

    def read(self, rel):
        return (ROOT / '_site' / rel).read_text(encoding='utf-8')

    def test_home_is_continuous_story_first(self):
        home = self.read('index.html')
        self.assertIn('data-layout="continuous-story-first"', home)
        self.assertIn('class="lead-grid"', home)
        self.assertIn('class="headline-strip"', home)
        self.assertIn('În Vâlcea, acum', home)
        self.assertIn('Ediție continuă', home)

    def test_home_has_editorial_navigation(self):
        home = self.read('index.html')
        self.assertIn('Navigație principală', home)
        self.assertIn('ACTUALITATE', home)
        self.assertIn('EVENIMENTE', home)
        self.assertIn('ENERGIE', home)

    def test_article_contract(self):
        article = self.read('stiri/buila-vanturarita-accident-20260822/index.html')
        self.assertIn('class="article-body"', article)
        self.assertIn('Surse și documente', article)
        self.assertIn('Distribuie articolul', article)
        self.assertIn('Redacția VÂLCEA CLAR', article)
        self.assertIn(
            '<link rel="canonical" href="https://valceaclar.ro/stiri/buila-vanturarita-accident-20260822/">',
            article,
        )
        self.assertIn('<meta name="robots" content="max-image-preview:large">', article)
        self.assertIn('<meta property="og:type" content="article">', article)

    def test_newsarticle_schema_matches_visible_article(self):
        article = self.read('stiri/buila-vanturarita-accident-20260822/index.html')
        match = re.search(r'<script type="application/ld\+json">(.+?)</script>', article)
        self.assertIsNotNone(match)
        schema = json.loads(match.group(1))
        canonical = 'https://valceaclar.ro/stiri/buila-vanturarita-accident-20260822/'
        self.assertEqual(schema['@type'], 'NewsArticle')
        self.assertEqual(schema['url'], canonical)
        self.assertEqual(schema['mainEntityOfPage']['@id'], canonical)
        self.assertEqual(schema['headline'], 'Accident mortal în Buila–Vânturarița: o mașină a căzut circa 300 de metri într-o prăpastie')
        self.assertEqual(schema['datePublished'], '2026-08-23T09:47:11+03:00')
        self.assertEqual(schema['dateModified'], schema['datePublished'])
        self.assertEqual(schema['author']['name'], 'Redacția VÂLCEA CLAR')
        self.assertTrue(schema['isAccessibleForFree'])

    def test_small_context_image_is_not_promoted_as_discover_image(self):
        article = self.read('stiri/cj_valcea_sedinte_publice-e1942667857ec69d/index.html')
        match = re.search(r'<script type="application/ld\+json">(.+?)</script>', article)
        schema = json.loads(match.group(1))
        self.assertNotIn('image', schema)
        self.assertNotIn('<meta property="og:image"', article)

    def test_all_routes_allow_large_previews(self):
        for page in (ROOT / '_site').rglob('*.html'):
            with self.subTest(page=page):
                text = page.read_text(encoding='utf-8')
                if 'utility-candidate-page' in text:
                    self.assertIn('<meta name="robots" content="noindex,nofollow">', text)
                else:
                    self.assertIn('<meta name="robots" content="max-image-preview:large">', text)

    def test_candidate_locality_utility_is_fail_closed(self):
        page = self.read('instrumente/maine-in-localitatea-ta/index.html')
        self.assertIn('Instrument în test', page)
        self.assertIn('candidate_only', page)
        self.assertIn('nu este o știre publicată', page)
        self.assertIn('<meta name="robots" content="noindex,nofollow">', page)

    def test_candidate_locality_selector_covers_all_uats(self):
        page = self.read('instrumente/maine-in-localitatea-ta/index.html')
        options = re.findall(r'<option value="([^"]+)" data-uat-type=', page)
        self.assertEqual(len(options), 89)
        self.assertEqual(len(set(options)), 89)
        self.assertIn('Râmnicu Vâlcea', options)
        self.assertIn('Drăgășani', options)

    def test_locality_preference_is_session_only(self):
        page = self.read('instrumente/maine-in-localitatea-ta/index.html')
        self.assertIn('sessionStorage', page)
        self.assertNotIn('localStorage', page)
        self.assertNotIn('visitor_id', page)
        self.assertIn('nu creăm un identificator persistent', page)

    def test_candidate_route_is_excluded_from_sitemap(self):
        sitemap = self.read('sitemap.xml')
        self.assertNotIn('/instrumente/maine-in-localitatea-ta/', sitemap)

    def test_site_verifier_still_passes(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / 'scripts' / 'verify.py')],
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
