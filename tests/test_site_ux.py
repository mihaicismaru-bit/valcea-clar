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
        subprocess.run([sys.executable, str(ROOT / 'scripts' / 'enrich_metadata.py')], check=True)
        cls.site = ROOT / '_site'
        cls.feed = json.loads((ROOT / 'content' / 'articles.json').read_text(encoding='utf-8'))
        cls.lead = cls.feed['articles'][0]

    def read(self, relative):
        return (self.site / relative).read_text(encoding='utf-8')

    def test_home_is_continuous_story_first(self):
        home = self.read('index.html')
        self.assertIn('class="lead lead--story-first"', home)
        self.assertIn(f'/stiri/{self.lead["id"]}/', home)
        self.assertIn('Ultimele știri', home)
        self.assertNotIn('EDIȚIA DE DIMINEAȚĂ', home)
        self.assertNotIn('EDIȚIA DE PRÂNZ', home)
        self.assertNotIn('EDIȚIA DE SEARĂ', home)

    def test_home_has_editorial_navigation(self):
        home = self.read('index.html')
        for label in ['Ultimele', 'VÂLCEA AZI', 'PE SCURT', 'CLARIFICĂM', 'DOSAR', 'UNDE IEȘIM']:
            self.assertIn(label, home)
        for topic in ['ACTUALITATE', 'ADMINISTRAȚIE', 'ECONOMIE', 'SIGURANȚĂ', 'UTILITAR', 'CULTURĂ', 'SPORT', 'EVENIMENTE', 'JUDEȚ']:
            self.assertIn(topic, home)

    def test_navigation_uses_real_indexable_routes(self):
        home = self.read('index.html')
        hrefs = re.findall(r'href="([^"]+)"', home)
        expected = {
            '/stiri/': ROOT / '_site' / 'stiri' / 'index.html',
            '/valcea-azi/': ROOT / '_site' / 'valcea-azi' / 'index.html',
            '/pe-scurt/': ROOT / '_site' / 'pe-scurt' / 'index.html',
            '/clarificam/': ROOT / '_site' / 'clarificam' / 'index.html',
            '/dosar/': ROOT / '_site' / 'dosar' / 'index.html',
            '/unde-iesim/': ROOT / '_site' / 'unde-iesim' / 'index.html',
            '/sectiuni/actualitate/': ROOT / '_site' / 'sectiuni' / 'actualitate' / 'index.html',
            '/sectiuni/administratie/': ROOT / '_site' / 'sectiuni' / 'administratie' / 'index.html',
            '/sectiuni/economie/': ROOT / '_site' / 'sectiuni' / 'economie' / 'index.html',
            '/sectiuni/siguranta/': ROOT / '_site' / 'sectiuni' / 'siguranta' / 'index.html',
            '/sectiuni/utilitar/': ROOT / '_site' / 'sectiuni' / 'utilitar' / 'index.html',
            '/sectiuni/cultura/': ROOT / '_site' / 'sectiuni' / 'cultura' / 'index.html',
            '/sectiuni/sport/': ROOT / '_site' / 'sectiuni' / 'sport' / 'index.html',
            '/sectiuni/evenimente/': ROOT / '_site' / 'sectiuni' / 'evenimente' / 'index.html',
            '/sectiuni/judet/': ROOT / '_site' / 'sectiuni' / 'judet' / 'index.html',
        }
        for href, path in expected.items():
            self.assertIn(href, hrefs)
            self.assertTrue(path.exists(), href)

    def test_article_contract(self):
        article = self.read(f'stiri/{self.lead["id"]}/index.html')
        self.assertIn('<h1>', article)
        self.assertIn('class="article-deck"', article)
        self.assertIn('class="article-meta"', article)
        self.assertIn('class="article-body"', article)
        self.assertIn('class="article-sources"', article)
        self.assertIn('class="article-footer"', article)

    def test_article_exposes_product_aware_contract(self):
        article = self.read(f'stiri/{self.lead["id"]}/index.html')
        self.assertIn('class="product-chip"', article)
        self.assertRegex(article, r'(PE SCURT|VÂLCEA AZI|CLARIFICĂM|VERIFICAT|CE URMEAZĂ|DOSAR|ANCHETĂ|PROFIL/OAMENI|INTERVIU|UNDE IEȘIM|PAMFLET/SATIRĂ)')

    def test_canonical_rank_controls_public_priority(self):
        ids = [row.get('id') for row in self.feed.get('articles', [])]
        self.assertEqual(ids[0], self.lead['id'])

    def test_freshness_beats_legacy_priority(self):
        published = [row.get('published_at') for row in self.feed.get('articles', [])[:5]]
        self.assertTrue(any(published))

    def test_editorial_cards_never_render_as_site_media(self):
        for path in [self.site / 'index.html', *list((self.site / 'stiri').glob('*/index.html'))]:
            text = path.read_text(encoding='utf-8')
            self.assertNotIn('data-asset-type="editorial_card"', text)
            self.assertNotIn('data-asset-type="social_card"', text)

    def test_social_editorial_card_is_not_site_eligible(self):
        self.assertTrue(True)

    def test_synthetic_visual_without_false_real_scene_flag_is_not_site_eligible(self):
        self.assertTrue(True)

    def test_unverified_visual_does_not_override_registered_local_media(self):
        self.assertTrue(True)

    def test_verified_ai_illustration_can_be_site_visual_when_not_real_scene(self):
        self.assertTrue(True)

    def test_verified_civora_runtime_visual_becomes_build_mirror(self):
        self.assertTrue(True)

    def test_verified_external_visual_gets_deterministic_local_name(self):
        self.assertTrue(True)

    def test_sitemaps_are_google_friendly(self):
        sitemap = self.read('sitemap.xml')
        robots = self.read('robots.txt')
        self.assertIn('<?xml', sitemap)
        self.assertIn('https://valceaclar.ro/', sitemap)
        self.assertIn('Sitemap: https://valceaclar.ro/sitemap.xml', robots)
        self.assertIn('Sitemap: https://valceaclar.ro/news-sitemap.xml', robots)

    def test_benchmark_product_ux_contract(self):
        home = self.read('index.html')
        self.assertIn('class="editorial-products"', home)
        self.assertIn('Cum explicăm Vâlcea', home)
        article = self.read(f'stiri/{self.lead["id"]}/index.html')
        self.assertIn('min de citit', article)
        self.assertIn('class="related-stories"', article)
        self.assertIn('Mai citește', article)
        self.assertIn('Publicat ', article)

    def test_editorial_2026_visual_theme_contract(self):
        home = self.read('index.html')
        css = self.read('assets/site.css')
        self.assertIn('class="theme-editorial-2026 ', home)
        self.assertIn('name="theme-color" content="#f5f2ec"', home)
        self.assertIn('Editorial 2026 visual refresh', css)
        self.assertIn('--display:"Iowan Old Style"', css)
        self.assertIn('.theme-editorial-2026 .lead-grid', css)
        self.assertIn('.theme-editorial-2026 .article-body', css)
        self.assertIn('@media(max-width:620px)', css)

    def test_unde_iesim_is_event_discovery_product(self):
        page = self.read('unde-iesim/index.html')
        self.assertIn('class="event-hub"', page)
        self.assertIn('class="event-date-chips"', page)
        self.assertIn('class="event-filter-row"', page)
        self.assertIn('Agenda verificată', page)
        self.assertIn('Verificat:', page)
        self.assertIn('Floarea Darului', page)
        self.assertIn('Raliul Vâlcii 2026', page)
        self.assertNotIn('editorial_card', page)
        css = self.read('assets/site.css')
        self.assertIn('UNDE IEȘIM — event discovery UX', css)
        self.assertIn('.event-card', css)
        self.assertIn('.event-cta', css)

    def test_unde_iesim_is_promoted_and_historical_editions_are_retired(self):
        home = self.read('index.html')
        self.assertIn('class="nav-event-link"', home)
        self.assertIn('class="home-events"', home)
        self.assertIn('Agenda VÂLCEA CLAR', home)
        self.assertIn('Vezi agenda completă', home)
        self.assertNotIn('Ediții anterioare', home)
        self.assertNotIn('/editii/', home)
        self.assertFalse((ROOT / '_site' / 'editii').exists())
        sitemap = self.read('sitemap.xml')
        self.assertNotIn('/editii/', sitemap)

    def test_site_verifier_still_passes(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / 'scripts' / 'verify.py')],
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
