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

    def test_site_verifier_still_passes(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / 'scripts' / 'verify.py')],
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
