import json
import subprocess
import sys
import unittest
import xml.etree.ElementTree as ET
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

    def test_article_exposes_product_aware_contract(self):
        article_id = self.lead['id']
        article = self.read(f'stiri/{article_id}/index.html')
        self.assertIn('data-product="', article)
        self.assertIn('class="product-badge"', article)
        self.assertIn('class="section-badge"', article)
        css = self.read('assets/site.css')
        self.assertIn('Product-aware editorial grammar', css)
        self.assertIn('article[data-product="DOSAR"]', css)
        self.assertIn('article[data-product="CLARIFICĂM"]', css)
        self.assertIn('article[data-product="PAMFLET/SATIRĂ"]', css)

    def test_editorial_cards_never_render_as_site_media(self):
        home = self.read('index.html')
        banned = ('Card editorial construit', 'VÂLCEA CLAR — card editorial')
        for marker in banned:
            self.assertNotIn(marker, home)
        for article in self.articles:
            fields = ' '.join(str(article.get(key) or '').lower() for key in (
                'image_caption', 'image_credit', 'image_rights_basis',
                'image_source_url', 'image_origin_url', 'image_fetch_url',
                'image_kind', 'visual_type', 'asset_type',
            ))
            if any(marker in fields for marker in (
                'card editorial', 'editorial card', 'editorial_card',
                'social card', 'social_card', 'original_editorial_layout',
                '/social/editorial/', 'social/editorial',
            )):
                page = self.read(f'stiri/{article["id"]}/index.html')
                visible = page.split('<main id="main">', 1)[1].split('</main>', 1)[0]
                self.assertNotIn(str(article.get('image') or ''), visible)
                self.assertNotIn(str(article.get('image_caption') or ''), visible)

    def test_navigation_uses_real_indexable_routes(self):
        home = self.read('index.html')
        self.assertIn('aria-label="Navigație principală"', home)
        self.assertIn('aria-label="Secțiuni tematice"', home)
        self.assertNotIn('href="/stiri/#', home)
        for href in ('/valcea-azi/', '/pe-scurt/', '/clarificam/', '/dosar/', '/sectiuni/administratie/'):
            self.assertIn(f'href="{href}"', home)
        for rel in ('valcea-azi/index.html', 'pe-scurt/index.html', 'clarificam/index.html', 'dosar/index.html', 'sectiuni/administratie/index.html'):
            self.assertTrue((ROOT / '_site' / rel).is_file(), rel)

    def test_sitemaps_are_google_friendly(self):
        sitemap = ROOT / '_site' / 'sitemap.xml'
        news = ROOT / '_site' / 'news-sitemap.xml'
        self.assertTrue(sitemap.is_file())
        self.assertTrue(news.is_file())
        root = ET.parse(sitemap).getroot()
        ns = {'s': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        urls = root.findall('s:url', ns)
        locs = [row.find('s:loc', ns).text for row in urls]
        self.assertEqual(len(locs), len(set(locs)))
        self.assertTrue(all('#' not in value for value in locs))
        self.assertIn('https://valceaclar.ro/clarificam/', locs)
        self.assertIn('https://valceaclar.ro/sectiuni/administratie/', locs)
        article_loc = f'https://valceaclar.ro/stiri/{self.lead["id"]}/'
        row = next(row for row in urls if row.find('s:loc', ns).text == article_loc)
        self.assertIsNotNone(row.find('s:lastmod', ns))

        news_root = ET.parse(news).getroot()
        news_ns = {
            's': 'http://www.sitemaps.org/schemas/sitemap/0.9',
            'n': 'http://www.google.com/schemas/sitemap-news/0.9',
        }
        news_urls = news_root.findall('s:url', news_ns)
        self.assertGreaterEqual(len(news_urls), 1)
        self.assertTrue(any(
            row.find('s:loc', news_ns).text == article_loc
            for row in news_urls
        ))
        robots = self.read('robots.txt')
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
