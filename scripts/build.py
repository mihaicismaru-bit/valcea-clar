#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime
from urllib.parse import quote
import html
import json
import os
import shutil

from media_assets import materialize_media

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '_site'
C = ROOT / 'content'
BASE = os.getenv('VALCEA_CLAR_BASE_PATH', '').rstrip('/')
PREVIEW = os.getenv('VALCEA_CLAR_PREVIEW', '') == '1'
SITE = 'https://valceaclar.ro'


def load(name):
    return json.loads((C / name).read_text(encoding='utf-8'))


def h(value):
    return html.escape(str(value), quote=True)


def u(path):
    path = '/' + str(path).lstrip('/')
    return (BASE + path) if BASE else path


def route_url(path='/'):
    path = '/' + str(path).lstrip('/')
    if path != '/' and not path.endswith('/'):
        path += '/'
    return SITE + path


def pretty_date(value):
    try:
        dt = datetime.fromisoformat(value)
        months = ['ianuarie', 'februarie', 'martie', 'aprilie', 'mai', 'iunie', 'iulie', 'august', 'septembrie', 'octombrie', 'noiembrie', 'decembrie']
        return f'{dt.day} {months[dt.month - 1]} {dt.year}, {dt:%H:%M}'
    except (TypeError, ValueError):
        return str(value or '')


def story_href(article):
    return u('/stiri/' + h(article['id']) + '/')


def image_html(article, hero=False):
    name = article.get('image')
    if not name:
        return '<div class="no-photo" aria-hidden="true">VÂLCEA CLAR</div>' if hero else ''
    caption = article.get('image_caption', 'Imagine de context din arhiva VÂLCEA CLAR.')
    return (
        '<figure class="story-media">'
        f'<img class="thumb" src="{u("/media/" + h(name))}" alt="{h(caption)}" loading="{"eager" if hero else "lazy"}">'
        f'<figcaption class="photo-note">{h(caption)}</figcaption>'
        '</figure>'
    )


def story_meta(article, compact=False):
    label = pretty_date(article.get('published'))
    if compact:
        return f'<div class="meta">{h(label)}</div>'
    return f'<div class="story-meta"><span>Redacția VÂLCEA CLAR</span><span>{h(label)}</span></div>'


articles = sorted(
    load('articles.json')['articles'],
    key=lambda a: (a.get('priority', 0), a.get('published', '')),
    reverse=True,
)
legal = load('legal.json')
media = {item['file']: item for item in load('media.json')}
css = (C / 'site.css').read_text(encoding='utf-8')
sections = []
for article in articles:
    section = article.get('section', 'ȘTIRI')
    if section not in sections:
        sections.append(section)

if OUT.exists():
    shutil.rmtree(OUT)
OUT.mkdir()
(OUT / 'assets').mkdir()
(OUT / 'assets/site.css').write_text(css, encoding='utf-8')
materialize_media(OUT / 'media')

section_links = ''.join(
    f'<a href="{u("/stiri/")}#{h(section.lower())}">{h(section)}</a>'
    for section in sections[:6]
)
nav = (
    '<nav class="nav" aria-label="Navigație principală">'
    f'<a href="{u("/")}">Acasă</a>'
    f'<a href="{u("/stiri/")}">Ultimele</a>'
    f'{section_links}'
    f'<a href="{u("/despre/")}">Despre</a>'
    '</nav>'
)


def canonical_article_image(article):
    """Return a crawlable image only when it meets the canonical Discover policy."""
    name = article.get('image')
    asset = media.get(name) if name else None
    if not asset or not asset.get('local_only') or not asset.get('rights_basis') or not asset.get('credit'):
        return None
    width = int(asset.get('width') or 0)
    height = int(asset.get('height') or 0)
    ratio = (width / height) if height else 0
    if width < 1200 or width * height <= 300_000 or not 1.65 <= ratio <= 1.9:
        return None
    return SITE + '/media/' + quote(name)


def news_article_schema(article, canonical, image_url=None):
    published = article.get('published')
    modified = article.get('updated') or published
    data = {
        '@context': 'https://schema.org',
        '@type': 'NewsArticle',
        'mainEntityOfPage': {'@type': 'WebPage', '@id': canonical},
        'url': canonical,
        'headline': article['headline'],
        'description': article['dek'],
        'datePublished': published,
        'dateModified': modified,
        'articleSection': article.get('section', 'ȘTIRI'),
        'inLanguage': 'ro-RO',
        'isAccessibleForFree': True,
        'author': {
            '@type': 'Organization',
            'name': 'Redacția VÂLCEA CLAR',
            'url': route_url('/despre/'),
        },
        'publisher': {
            '@type': 'Organization',
            'name': 'VÂLCEA CLAR',
            'url': route_url('/'),
        },
    }
    if image_url:
        data['image'] = [image_url]
    return json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')


def shell(title, body, desc='Știri locale verificate din Vâlcea.', canonical_path='/', body_class='', og_type='website', og_image=None, extra_head=''):
    robots_value = 'noindex,nofollow' if PREVIEW else 'max-image-preview:large'
    robots = f'<meta name="robots" content="{robots_value}">'
    canonical = route_url(canonical_path)
    image_meta = f'<meta property="og:image" content="{h(og_image)}">' if og_image else ''
    return f'''<!doctype html>
<html lang="ro">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{h(title)}</title>
<meta name="description" content="{h(desc)}">
{robots}
<link rel="canonical" href="{h(canonical)}">
<meta property="og:site_name" content="VÂLCEA CLAR">
<meta property="og:type" content="{h(og_type)}">
<meta property="og:title" content="{h(title)}">
<meta property="og:description" content="{h(desc)}">
<meta property="og:url" content="{h(canonical)}">
{image_meta}
{extra_head}
<link rel="stylesheet" href="{u('/assets/site.css')}">
</head>
<body class="{h(body_class)}">
<a class="skip" href="#main">Sari la conținut</a>
<header class="site-header">
  <div class="mast">
    <div class="mast-meta">Vâlcea · publicație locală</div>
    <a class="brand" href="{u('/')}">VÂLCEA CLAR</a>
    <div class="tag">Fapte. Documente. Context.</div>
  </div>
  {nav}
</header>
<main id="main">{body}</main>
<footer>
  <strong>VÂLCEA CLAR</strong> · redactie@valceaclar.ro
  <div class="footer-links"><a href="{u('/despre/')}">Despre</a> · <a href="{u('/termeni/')}">Termeni</a> · <a href="{u('/confidentialitate/')}">Confidențialitate</a></div>
</footer>
</body>
</html>'''


def mini_story(article):
    return (
        '<article class="rail-story">'
        f'<div class="kicker">{h(article["section"])}</div>'
        f'<strong><a href="{story_href(article)}">{h(article["headline"])}</a></strong>'
        f'{story_meta(article, True)}'
        '</article>'
    )


def stream_story(article):
    media = image_html(article) if article.get('image') else ''
    return (
        '<article class="stream-story">'
        f'<div class="stream-copy"><div class="kicker">{h(article["section"])}</div>'
        f'<h3><a href="{story_href(article)}">{h(article["headline"])}</a></h3>'
        f'<p>{h(article["dek"])}</p>{story_meta(article, True)}</div>'
        f'<div class="stream-media">{media}</div>'
        '</article>'
    )


lead = articles[0]
rail_articles = articles[1:4]
stream_articles = articles[4:] if len(articles) > 4 else articles[1:]
latest_links = ''.join(
    f'<a href="{story_href(a)}"><span>{h(a["section"])}</span>{h(a["headline"])}</a>'
    for a in articles[1:4]
)

home = (
    '<div data-layout="continuous-story-first">'
    '<div class="status"><div><b>Ediție continuă</b> · Vâlcea, România</div>'
    f'<div>Ultima actualizare: {h(pretty_date(articles[0].get("published")))}</div></div>'
    f'<aside class="headline-strip" aria-label="Pe scurt"><span>Pe scurt</span>{latest_links}</aside>'
    '<section class="lead-grid" aria-label="Principal">'
    '<article class="hero">'
    f'{image_html(lead, True)}'
    f'<div class="kicker">{h(lead["section"])}</div>'
    f'<h1><a href="{story_href(lead)}">{h(lead["headline"])}</a></h1>'
    f'<p class="dek">{h(lead["dek"])}</p>{story_meta(lead)}'
    '</article>'
    '<aside class="rail"><h2>Ultimele</h2>'
    + ''.join(mini_story(a) for a in rail_articles)
    + f'<a class="more-link" href="{u("/stiri/")}">Toate știrile →</a></aside>'
    '</section>'
    '<section class="section latest-section">'
    '<div class="section-head"><h2>În Vâlcea, acum</h2><a href="' + u('/stiri/') + '">Flux complet →</a></div>'
    '<div class="story-stream">' + ''.join(stream_story(a) for a in stream_articles) + '</div>'
    '</section>'
)

for section in sections:
    section_articles = [a for a in articles if a.get('section') == section]
    if not section_articles:
        continue
    home += (
        f'<section class="section section-block" id="home-{h(section.lower())}">'
        f'<div class="section-head"><h2>{h(section.title())}</h2>'
        f'<a href="{u("/stiri/")}#{h(section.lower())}">Vezi secțiunea →</a></div>'
        '<div class="cards">'
        + ''.join(
            '<article class="card">'
            f'{image_html(a)}<div class="kicker">{h(a["section"])}</div>'
            f'<h3><a href="{story_href(a)}">{h(a["headline"])}</a></h3>'
            f'<p>{h(a["dek"])}</p>{story_meta(a, True)}'
            '</article>'
            for a in section_articles[:3]
        )
        + '</div></section>'
    )
home += '</div>'

(OUT / 'index.html').write_text(
    shell('VÂLCEA CLAR — Știri din Vâlcea', home, canonical_path='/'),
    encoding='utf-8',
)

rows = ''
for section in sections:
    section_articles = [a for a in articles if a.get('section') == section]
    rows += f'<section class="news-section" id="{h(section.lower())}"><div class="section-head"><h2>{h(section.title())}</h2></div>'
    for a in section_articles:
        thumb = image_html(a) if a.get('image') else ''
        rows += (
            '<article class="list-row">'
            f'<div class="list-media">{thumb}</div>'
            f'<div><div class="kicker">{h(a["section"])}</div><h2><a href="{story_href(a)}">{h(a["headline"])}</a></h2>'
            f'<p>{h(a["dek"])}</p>{story_meta(a, True)}</div></article>'
        )
    rows += '</section>'

stiri_body = (
    '<div class="page-head"><div class="eyebrow">Flux editorial</div><h1 class="page-title">Ultimele știri</h1>'
    '<p class="page-dek">Informații locale ordonate editorial, cu surse identificabile și actualizări continue.</p></div>'
    f'<div class="list">{rows}</div>'
)


def write_route(path, text):
    directory = OUT / path.strip('/')
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'index.html').write_text(text, encoding='utf-8')


write_route('stiri', shell('Știri — VÂLCEA CLAR', stiri_body, canonical_path='/stiri/'))

for article in articles:
    canonical_path = '/stiri/' + article['id'] + '/'
    canonical = route_url(canonical_path)
    canonical_image = canonical_article_image(article)
    published = article.get('published', '')
    modified = article.get('updated') or published
    article_head = (
        f'<meta property="article:published_time" content="{h(published)}">\n'
        f'<meta property="article:modified_time" content="{h(modified)}">\n'
        f'<script type="application/ld+json">{news_article_schema(article, canonical, canonical_image)}</script>'
    )
    fb = 'https://www.facebook.com/sharer/sharer.php?u=' + quote(canonical, safe='')
    wa = 'https://wa.me/?text=' + quote(article['headline'] + ' ' + canonical, safe='')
    mail = 'mailto:?subject=' + quote(article['headline']) + '&body=' + quote(canonical)
    paragraphs = ''.join(f'<p>{h(p)}</p>' for p in article['paragraphs'])
    sources = ''.join(
        f'<li><a href="{h(source["url"])}" rel="nofollow noopener">{h(source["name"])}</a></li>'
        for source in article['sources']
    )
    body = (
        '<article class="article">'
        f'<a class="back top-back" href="{u("/stiri/")}">← Ultimele știri</a>'
        f'<div class="kicker">{h(article["section"])}</div>'
        f'<h1>{h(article["headline"])}</h1>'
        f'<p class="dek">{h(article["dek"])}</p>{story_meta(article)}'
        '<div class="share-bar" aria-label="Distribuie articolul"><span>Distribuie</span>'
        f'<a href="{h(fb)}" rel="nofollow noopener">Facebook</a>'
        f'<a href="{h(wa)}" rel="nofollow noopener">WhatsApp</a>'
        f'<a href="{h(mail)}">Email</a></div>'
        f'<div class="article-media">{image_html(article, True)}</div>'
        f'<div class="article-body">{paragraphs}</div>'
        f'<section class="sources"><h2>Surse și documente</h2><p>Materialul este construit pe surse identificabile. Linkurile de mai jos permit verificarea informațiilor.</p><ul>{sources}</ul></section>'
        f'<a class="back" href="{u("/stiri/")}">← Înapoi la flux</a>'
        '</article>'
    )
    write_route(
        'stiri/' + article['id'],
        shell(
            article['headline'] + ' — VÂLCEA CLAR',
            body,
            article['dek'],
            canonical_path,
            'article-page',
            'article',
            canonical_image,
            article_head,
        ),
    )

about = (
    '<div class="legal article"><div class="kicker">Despre publicație</div><h1>VÂLCEA CLAR</h1>'
    '<p class="dek">Publicație locală construită pentru informație clară, verificabilă și utilă.</p>'
    '<section><h2>Principiul editorial</h2><p>Separăm faptele confirmate de interpretări, folosim documente și surse identificabile și marcăm explicit limitele informației disponibile.</p></section>'
    '<section><h2>Publicare continuă</h2><p>Fluxul este actualizat pe măsură ce apar informații relevante. Automatizarea poate descoperi și pregăti materiale, însă controalele de risc rămân fail-closed.</p></section></div>'
)
write_route('despre', shell('Despre — VÂLCEA CLAR', about, canonical_path='/despre/'))

for slug in ['termeni', 'confidentialitate']:
    item = legal[slug]
    body = (
        '<div class="legal article">'
        f'<h1>{h(item["title"])}</h1><p class="dek">{h(item.get("dek", ""))}</p>'
        + ''.join(f'<section><h2>{h(sec[0])}</h2><p>{h(sec[1])}</p></section>' for sec in item['sections'])
        + '</div>'
    )
    write_route(slug, shell(item['title'] + ' — VÂLCEA CLAR', body, canonical_path='/' + slug + '/'))

(OUT / 'robots.txt').write_text(
    'User-agent: *\nDisallow: /\n' if PREVIEW else 'User-agent: *\nAllow: /\nSitemap: https://valceaclar.ro/sitemap.xml\n',
    encoding='utf-8',
)
urls = ['/', '/stiri/', '/despre/', '/termeni/', '/confidentialitate/'] + [f'/stiri/{a["id"]}/' for a in articles]
(OUT / 'sitemap.xml').write_text(
    '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    + ''.join(f'<url><loc>{SITE}{path}</loc></url>' for path in urls)
    + '</urlset>',
    encoding='utf-8',
)
print(f'Built {len(urls)} routes; {len(list((OUT / "media").glob("*.webp")))} local images; base={BASE or "/"}; preview={PREVIEW}.')
