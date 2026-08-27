import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SiteUXContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run([sys.executable, str(ROOT / 'scripts' / 'build.py')], check=True)
        subprocess.run([sys.executable, str(ROOT / 'scripts' / 'enrich_metadata.py')], check=True)
        cls.content = json.loads((ROOT / 'content' / 'articles.json').read_text(encoding='utf-8'))
        cls.articles = cls.content['articles']
        cls.lead = cls.articles[0]

    def read(self, rel):
        return (ROOT / '_site' / rel).read_text(encoding='utf-8')

    def test_home_is_continuous_story_first(self):
        home = self.read('index.html')
        self.assertIn('data-layout="continuous-story-first"', home)
        self.assertIn('class="lead-grid"', home)
        self.assertIn('class="headline-strip"', home)
        self.assertIn('În Vâlcea, acum', home)
        self.assertIn('Ediție continuă', home)
        self.assertIn('max-image-preview:large', home)
        self.assertIn('"@type":"NewsMediaOrganization"', home)

    def test_home_has_editorial_navigation(self):
        home = self.read('index.html')
        self.assertIn('Navigație principală', home)
        self.assertIn('Acasă', home)
        self.assertIn('Ultimele', home)
        self.assertIn('Despre', home)
        current_sections = {str(a.get('section', '')).strip() for a in self.articles if a.get('section')}
        self.assertTrue(current_sections)
        self.assertTrue(any(section in home for section in current_sections))

    def test_article_contract(self):
        article_id = self.lead['id']
        article = self.read(f'stiri/{article_id}/index.html')
        self.assertIn('class="article-body"', article)
        self.assertIn('Surse și documente', article)
        self.assertIn('Distribuie articolul', article)
        self.assertIn('Redacția VÂLCEA CLAR', article)
        self.assertIn(
            f'<link rel="canonical" href="https://valceaclar.ro/stiri/{article_id}/">',
            article,
        )
        self.assertIn('"@type":"NewsArticle"', article)
        self.assertIn('property="og:type" content="article"', article)
        self.assertIn('name="twitter:card"', article)
        self.assertIn('max-image-preview:large', article)

    def test_site_verifier_still_passes(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / 'scripts' / 'verify.py')],
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
