#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime, timedelta
from urllib.parse import quote
import html
import json
import os
import shutil
import unicodedata

from media_assets import materialize_media

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '_site'
C = ROOT / 'content'
BASE = os.getenv('VALCEA_CLAR_BASE_PATH', '').rstrip('/')
PREVIEW = os.getenv('VALCEA_CLAR_PREVIEW', '') == '1'
SITE = 'https://valceaclar.ro'
AVAILABLE_MEDIA = set()


def load(name):
    return json.loads((C / name).read_text(encoding='utf-8'))


def h(value):
    return html.escape(str(value), quote=True)


def xh(value):
    return html.escape(str(value), quote=False)


def slugify(value):
    normalized = unicodedata.normalize('NFKD', str(value or ''))
    ascii_value = normalized.encode('ascii', 'ignore').decode('ascii').lower()
    cleaned = ''.join(ch if ch.isalnum() else '-' for ch in ascii_value)
    return '-'.join(part for part in cleaned.split('-') if part)


def parse_dt(value):
    try:
        dt = datetime.fromisoformat(str(value or '').replace('Z', '+00:00'))
        return dt if dt.tzinfo else dt.astimezone()
    except (TypeError, ValueError):
        return None


def sitemap_lastmod(value):
    dt = parse_dt(value)
    return dt.isoformat(timespec='seconds') if dt else ''


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


def is_editorial_card(article):
    """Return True for social/editorial cards that must never render as site media."""
    if article.get('image_site_eligible') is False:
        return True
    fields = [
        article.get('image_caption'),
        article.get('image_credit'),
        article.get('image_rights_basis'),
        article.get('image_source_url'),
        article.get('image_origin_url'),
        article.get('image_fetch_url'),
        article.get('image_kind'),
        article.get('visual_type'),
        article.get('asset_type'),
    ]
    haystack = ' '.join(str(value or '').lower() for value in fields)
    markers = (
        'card editorial',
        'editorial card',
        'editorial_card',
        'social card',
        'social_card',
        'original_editorial_layout',
        '/social/editorial/',
        'social/editorial',
    )
    return any(marker in haystack for marker in markers)


def image_html(article, hero=False):
    name = article.get('image')
    if not name or name not in AVAILABLE_MEDIA or is_editorial_card(article):
        return ''
    caption = article.get('image_caption', 'Imagine de context din arhiva VÂLCEA CLAR.')
    return (
        '<figure class="story-media">'
        f'<img class="thumb" src="{u("/media/" + h(name))}" alt="{h(caption)}" loading="{"eager" if hero else "lazy"}">'
        f'<figcaption class="photo-note">{h(caption)}</figcaption>'
        '</figure>'
    )


def reading_time(article):
    text = ' '.join(str(value or '') for value in article.get('paragraphs') or [])
    words = len(text.split())
    return max(1, round(words / 220))


def story_meta(article, compact=False):
    published = pretty_date(article.get('published'))
    updated_raw = article.get('updated') or article.get('updated_at') or article.get('modified')
    updated = pretty_date(updated_raw) if updated_raw and str(updated_raw) != str(article.get('published')) else ''
    minutes = reading_time(article)
    if compact:
        return f'<div class="meta">{h(published)} · {minutes} min</div>'
    parts = [
        '<span>Redacția VÂLCEA CLAR</span>',
        f'<span>Publicat {h(published)}</span>',
        f'<span>{minutes} min de citit</span>',
    ]
    if updated:
        parts.append(f'<span>Actualizat {h(updated)}</span>')
    return '<div class="story-meta">' + ''.join(parts) + '</div>'


PRODUCTS = {
    'PE SCURT',
    'CLARIFICĂM',
    'VERIFICAT',
    'CE URMEAZĂ',
    'VÂLCEA AZI',
    'WEEKEND CLAR',
    'DOSAR',
    'UNDE IEȘIM',
    'PROFIL/OAMENI',
    'ANCHETĂ',
    'PAMFLET/SATIRĂ',
}
PRODUCT_ALIASES = {
    'NEWS': 'VÂLCEA AZI',
    'STRAIGHT NEWS': 'VÂLCEA AZI',
    'BREAKING': 'VÂLCEA AZI',
    'SERVICE ALERT': 'PE SCURT',
    'SERVICE NEWS': 'PE SCURT',
    'EXPLAINER': 'CLARIFICĂM',
    'DECISION DIGEST': 'CLARIFICĂM',
    'FACT CHECK': 'VERIFICAT',
    'VERIFIED DATA': 'VERIFICAT',
    'VERIFICAT DIN DATE': 'VERIFICAT',
    'STATUS CHECK': 'CE URMEAZĂ',
    'WHAT HAPPENED NEXT': 'CE URMEAZĂ',
    'PROJECT TRACKER': 'CE URMEAZĂ',
    'PERMIT FOLLOWUP': 'CE URMEAZĂ',
    'UPCOMING EVENTS': 'UNDE IEȘIM',
    'EVENT GUIDE': 'UNDE IEȘIM',
    'MONEY TRACE': 'DOSAR',
    'DOSSIER': 'DOSAR',
    'PROFILE': 'PROFIL/OAMENI',
    'PEOPLE': 'PROFIL/OAMENI',
    'INVESTIGATION': 'ANCHETĂ',
    'SATIRE': 'PAMFLET/SATIRĂ',
    'PAMPHLET': 'PAMFLET/SATIRĂ',
    'WEEKEND': 'WEEKEND CLAR',
}
PRODUCT_SLUGS = {
    'PE SCURT': 'pe-scurt',
    'CLARIFICĂM': 'clarificam',
    'VERIFICAT': 'verificat',
    'CE URMEAZĂ': 'ce-urmeaza',
    'VÂLCEA AZI': 'valcea-azi',
    'WEEKEND CLAR': 'weekend-clar',
    'DOSAR': 'dosar',
    'UNDE IEȘIM': 'unde-iesim',
    'PROFIL/OAMENI': 'profil-oameni',
    'ANCHETĂ': 'ancheta',
    'PAMFLET/SATIRĂ': 'pamflet-satira',
}
PRODUCT_DESCRIPTIONS = {
    'PE SCURT': 'Informația esențială, verificată și pusă rapid în context.',
    'CLARIFICĂM': 'Explicăm ce rezultă din fapte și documente și separăm explicit ceea ce rămâne necunoscut.',
    'VERIFICAT': 'Afirmațiile și cifrele sunt confruntate cu sursele disponibile, iar limitele verificării rămân vizibile.',
    'CE URMEAZĂ': 'Urmărim pașii următori, termenele și întrebările care rămân deschise.',
    'WEEKEND CLAR': 'Selecție de idei și informații utile pentru timpul liber, verificate editorial.',
    'DOSAR': 'Context extins, documente, cronologie și legături între decizii, bani, proiecte și actori.',
    'UNDE IEȘIM': 'Ghid practic de evenimente și locuri, cu informațiile utile și data verificării.',
    'PROFIL/OAMENI': 'Un portret jurnalistic construit din fapte, context și contribuții relevante pentru comunitate.',
    'ANCHETĂ': 'Documentare aprofundată, cu trasabilitatea probelor și drept la replică acolo unde este necesar.',
    'PAMFLET/SATIRĂ': 'Text satiric bazat pe un nucleu factual verificat; exagerarea editorială este separată de fapte.',
}


def _product_token(value):
    return ' '.join(str(value or '').strip().upper().replace('_', ' ').replace('-', ' ').split())


def article_product(article):
    raw = (
        article.get('editorial_product')
        or article.get('product_type')
        or article.get('product')
        or article.get('format')
        or ''
    )
    token = _product_token(raw)
    # An explicit reader-facing product is authoritative. Internal writer
    # formats are aliases only; they must not erase a durable public product
    # already encoded in the canonical story identity.
    if token in PRODUCTS:
        return token

    story_id = str(article.get('id') or '').lower()
    conservative_markers = (
        ('pamflet', 'PAMFLET/SATIRĂ'),
        ('satira', 'PAMFLET/SATIRĂ'),
        ('ancheta', 'ANCHETĂ'),
        ('dosar', 'DOSAR'),
        ('profil-', 'PROFIL/OAMENI'),
        ('weekend-', 'WEEKEND CLAR'),
    )
    for marker, product in conservative_markers:
        if marker in story_id:
            return product

    if token in PRODUCT_ALIASES:
        return PRODUCT_ALIASES[token]
    return 'VÂLCEA AZI'


def product_slug(article):
    return PRODUCT_SLUGS[article_product(article)]


def product_path(product):
    return '/' + PRODUCT_SLUGS[product] + '/'


def section_slug(section):
    return slugify(section) or 'stiri'


def section_path(section):
    return '/sectiuni/' + section_slug(section) + '/'


def product_kicker(article):
    product = article_product(article)
    section = str(article.get('section') or 'ȘTIRI')
    return (
        '<div class="kicker product-kicker">'
        f'<span class="product-badge">{h(product)}</span>'
        f'<span class="section-badge">{h(section)}</span>'
        '</div>'
    )


def product_signpost(article):
    product = article_product(article)
    description = PRODUCT_DESCRIPTIONS.get(product)
    if not description:
        return ''
    return (
        f'<aside class="product-signpost" aria-label="Format editorial: {h(product)}">'
        f'<strong>{h(product)}</strong><span>{h(description)}</span></aside>'
    )


articles = sorted(
    load('articles.json')['articles'],
    key=lambda a: (a.get('priority', 0), a.get('published', '')),
    reverse=True,
)
legal = load('legal.json')
events_payload = load('events.json') if (C / 'events.json').exists() else {'events': []}
events = events_payload.get('events') or []
css = (C / 'site.css').read_text(encoding='utf-8')
sections = []
for article in articles:
    section = article.get('section', 'ȘTIRI')
    if section not in sections:
        sections.append(section)


def related_articles(article, limit=3):
    article_id = str(article.get('id') or '')
    product = article_product(article)
    section = str(article.get('section') or '')
    candidates = [row for row in articles if str(row.get('id') or '') != article_id]
    candidates.sort(
        key=lambda row: (
            1 if article_product(row) == product else 0,
            1 if str(row.get('section') or '') == section else 0,
            int(row.get('priority') or 0),
            str(row.get('published') or ''),
        ),
        reverse=True,
    )
    return candidates[:limit]


def related_block(article):
    rows = related_articles(article)
    if not rows:
        return ''
    items = ''.join(
        '<li>'
        f'<a href="{story_href(row)}"><span>{h(article_product(row))} · {h(row.get("section") or "ȘTIRI")}</span>'
        f'<strong>{h(row["headline"])}</strong></a>'
        '</li>'
        for row in rows
    )
    return (
        '<section class="related-stories"><div class="section-head"><h2>Mai citește</h2></div>'
        f'<ul>{items}</ul></section>'
    )

if OUT.exists():
    shutil.rmtree(OUT)
OUT.mkdir()
(OUT / 'assets').mkdir()
(OUT / 'assets/site.css').write_text(css, encoding='utf-8')
AVAILABLE_MEDIA = materialize_media(OUT / 'media')

available_products = {article_product(article) for article in articles}
product_nav_order = [
    'VÂLCEA AZI', 'PE SCURT', 'CLARIFICĂM', 'VERIFICAT',
    'CE URMEAZĂ', 'DOSAR', 'UNDE IEȘIM', 'PROFIL/OAMENI', 'ANCHETĂ'
]
primary_product_links = ''.join(
    f'<a href="{u(product_path(product))}">{h(product)}</a>'
    for product in product_nav_order if product in available_products
)
section_nav_order = [
    'ACTUALITATE', 'ADMINISTRAȚIE', 'ECONOMIE', 'SIGURANȚĂ',
    'UTILITAR', 'CULTURĂ', 'SPORT', 'EVENIMENTE', 'JUDEȚ'
]
topic_links = ''.join(
    f'<a href="{u(section_path(section))}">{h(section.replace("_", " "))}</a>'
    for section in section_nav_order if section in sections
)
nav = (
    '<div class="nav-stack">'
    '<nav class="nav nav-primary" aria-label="Navigație principală">'
    f'<a href="{u("/")}">Acasă</a>'
    f'<a href="{u("/stiri/")}">Ultimele</a>'
    f'{primary_product_links}'
    f'<a href="{u("/despre/")}">Despre</a>'
    '</nav>'
    '<nav class="nav nav-topics" aria-label="Secțiuni tematice">'
    '<span class="nav-label">Teme</span>'
    f'{topic_links}'
    '</nav>'
    '</div>'
)


def shell(title, body, desc='Știri locale verificate din Vâlcea.', canonical_path='/', body_class=''):
    robots = '<meta name="robots" content="noindex,nofollow">' if PREVIEW else ''
    canonical = route_url(canonical_path)
    return f'''<!doctype html>
<html lang="ro">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">\n<meta name="theme-color" content="#f5f2ec">
<title>{h(title)}</title>
<meta name="description" content="{h(desc)}">
{robots}
<link rel="canonical" href="{h(canonical)}">
<meta property="og:site_name" content="VÂLCEA CLAR">
<meta property="og:title" content="{h(title)}">
<meta property="og:description" content="{h(desc)}">
<meta property="og:url" content="{h(canonical)}">
<link rel="stylesheet" href="{u('/assets/site.css')}">
</head>
<body class="theme-editorial-2026 {h(body_class)}">
<a class="skip" href="#main">Sari la conținut</a>
<header class="site-header">
  <div class="mast">
    <div class="mast-meta">Vâlcea · publicație locală</div>
    <a class="brand" href="{u('/')}">VÂLCEA CLAR</a>
    <div class="tag">Ce se întâmplă. Ce știm. Ce contează.</div>
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
        f'{product_kicker(article)}'
        f'<strong><a href="{story_href(article)}">{h(article["headline"])}</a></strong>'
        f'{story_meta(article, True)}'
        '</article>'
    )


def stream_story(article):
    media = image_html(article) if article.get('image') else ''
    media_block = f'<div class="stream-media">{media}</div>' if media else ''
    no_media = ' no-media' if not media else ''
    return (
        f'<article class="stream-story{no_media}">'
        f'<div class="stream-copy">{product_kicker(article)}'
        f'<h3><a href="{story_href(article)}">{h(article["headline"])}</a></h3>'
        f'<p>{h(article["dek"])}</p>{story_meta(article, True)}</div>'
        f'{media_block}'
        '</article>'
    )


lead = articles[0]
rail_articles = articles[1:4]
stream_articles = articles[4:] if len(articles) > 4 else articles[1:]
latest_links = ''.join(
    f'<a href="{story_href(a)}"><span>{h(article_product(a))} · {h(a["section"])}</span>{h(a["headline"])}</a>'
    for a in articles[1:4]
)

home = (
    '<div data-layout="continuous-story-first">'
    '<section class="mission-strip" aria-label="Promisiunea editorială">'
    '<strong>VÂLCEA. CLAR.</strong><span>Ce se întâmplă.</span><span>Ce știm.</span><span>Ce contează.</span>'
    '</section>'
    '<div class="status"><div><b>Ediție continuă</b> · Redacție locală autonomă · tot județul Vâlcea</div>'
    f'<div>Ultima actualizare: {h(pretty_date(articles[0].get("published")))}</div></div>'
    f'<aside class="headline-strip" aria-label="Pe scurt"><span>Pe scurt</span>{latest_links}</aside>'
    '<section class="lead-grid" aria-label="Principal">'
    '<article class="hero">'
    f'{image_html(lead, True)}'
    f'{product_kicker(lead)}'
    f'<h1><a href="{story_href(lead)}">{h(lead["headline"])}</a></h1>'
    f'<p class="dek">{h(lead["dek"])}</p>{story_meta(lead)}'
    '</article>'
    '<aside class="rail"><h2>Ultimele</h2>'
    + ''.join(mini_story(a) for a in rail_articles)
    + f'<a class="more-link" href="{u("/stiri/")}">Toate știrile →</a></aside>'
    '</section>'
    '<section class="editorial-products" aria-label="Produse editoriale">'
    '<div class="section-head"><h2>Cum explicăm Vâlcea</h2><span>Formate diferite pentru nevoi diferite</span></div>'
    '<div class="product-grid">'
    + ''.join(
        (
            f'<a class="product-tile" href="{u(product_path(product))}">'
            f'<span>{h(product)}</span>'
            f'<strong>{h(next(row["headline"] for row in articles if article_product(row) == product))}</strong>'
            f'<small>{sum(1 for row in articles if article_product(row) == product)} materiale</small>'
            '</a>'
        )
        for product in product_nav_order
        if product in available_products
    )
    + '</div></section>'
    '<section class="service-grid" aria-label="Informație utilă">'
    '<div><b>TRAFIC</b><span>Drumuri, incidente, restricții</span></div>'
    '<div><b>UTILITĂȚI</b><span>Apă, energie, termoficare</span></div>'
    '<div><b>EVENIMENTE</b><span>Ce se întâmplă azi în județ</span></div>'
    '<div><b>DE URMĂRIT</b><span>Subiecte deschise și ce urmează</span></div>'
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
        f'<a href="{u(section_path(section))}">Vezi secțiunea →</a></div>'
        '<div class="cards">'
        + ''.join(
            '<article class="card">'
            f'{image_html(a)}{product_kicker(a)}'
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
            f'<div>{product_kicker(a)}<h2><a href="{story_href(a)}">{h(a["headline"])}</a></h2>'
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


def archive_page(title, description, page_articles, eyebrow='VÂLCEA CLAR'):
    rows = ''.join(stream_story(article) for article in page_articles)
    body = (
        f'<div class="page-head"><div class="eyebrow">{h(eyebrow)}</div>'
        f'<h1 class="page-title">{h(title)}</h1>'
        f'<p class="page-dek">{h(description)}</p></div>'
        f'<div class="story-stream archive-stream">{rows}</div>'
    )
    return body


def event_dt(event, key='start'):
    return parse_dt(event.get(key))


def event_category_slug(event):
    return slugify(event.get('category') or 'eveniment')


def event_card(event):
    start = event_dt(event)
    day = str(start.day) if start else '—'
    months_short = ['IAN', 'FEB', 'MAR', 'APR', 'MAI', 'IUN', 'IUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']
    month = months_short[start.month - 1] if start else ''
    time = start.strftime('%H:%M') if start and (start.hour or start.minute) else 'ora de verificat'
    venue = str(event.get('venue') or 'Loc de verificat')
    locality = str(event.get('locality') or 'Vâlcea')
    category = str(event.get('category') or 'Eveniment')
    story_id = str(event.get('story_id') or '')
    href = u('/stiri/' + h(story_id) + '/') if story_id else u('/unde-iesim/')
    ticket_url = str(event.get('ticket_url') or '').strip()
    cta = (
        f'<a class="event-cta event-cta--ticket" href="{h(ticket_url)}" rel="nofollow noopener">Bilete</a>'
        if ticket_url else
        f'<a class="event-cta" href="{href}">Detalii</a>'
    )
    price_status = str(event.get('price_status') or 'unknown')
    price = 'Preț de verificat' if price_status == 'unknown' else price_status
    return (
        '<article class="event-card">'
        f'<div class="event-date"><strong>{h(day)}</strong><span>{h(month)}</span></div>'
        '<div class="event-copy">'
        f'<div class="event-category">{h(category)}</div>'
        f'<h2><a href="{href}">{h(event.get("title") or "Eveniment")}</a></h2>'
        f'<div class="event-facts"><span>{h(time)}</span><span>{h(venue)}</span><span>{h(locality)}</span><span>{h(price)}</span></div>'
        f'<div class="event-freshness">Verificat: {h(pretty_date(event.get("checked_at")))}</div>'
        '</div>'
        f'<div class="event-action">{cta}</div>'
        '</article>'
    )


def event_discovery_page():
    upcoming = [
        event for event in events
        if str(event.get('status') or '').lower() not in {'cancelled', 'past'}
        and event_dt(event)
    ]
    upcoming.sort(key=lambda event: event_dt(event))
    categories = []
    for event in upcoming:
        category = str(event.get('category') or 'Eveniment')
        if category not in categories:
            categories.append(category)

    date_chips = (
        '<div class="event-date-chips" aria-label="Perioadă">'
        '<a href="#agenda">Următoarele</a>'
        '<a href="#septembrie">Septembrie</a>'
        '<a href="#octombrie">Octombrie</a>'
        '<a href="#noiembrie">Noiembrie</a>'
        '<a href="#decembrie">Decembrie</a>'
        '</div>'
    )
    category_chips = (
        '<div class="event-filter-row" aria-label="Categorii">'
        '<span>Filtre</span>'
        + ''.join(f'<a href="#cat-{h(slugify(category))}">{h(category)}</a>' for category in categories)
        + '</div>'
    )

    groups = []
    month_names = ['ianuarie', 'februarie', 'martie', 'aprilie', 'mai', 'iunie', 'iulie', 'august', 'septembrie', 'octombrie', 'noiembrie', 'decembrie']
    for month in range(9, 13):
        rows = [event for event in upcoming if event_dt(event).month == month]
        if not rows:
            continue
        groups.append(
            f'<section class="event-month" id="{month_names[month-1]}">'
            f'<div class="event-month-head"><h2>{h(month_names[month-1].title())}</h2><span>{len(rows)} evenimente verificate</span></div>'
            + ''.join(event_card(event) for event in rows)
            + '</section>'
        )

    empty_note = ''
    if len(upcoming) < 6:
        empty_note = (
            '<aside class="event-inventory-note"><strong>Calendar în extindere</strong>'
            '<p>Publicăm numai evenimente pentru care data și sursa au fost verificate. '
            'Redacția completează agenda pe măsură ce organizatorii publică programele și accesul.</p></aside>'
        )
    return (
        '<div class="event-hub">'
        '<div class="event-hero"><div class="eyebrow">Ghid local · VÂLCEA CLAR</div>'
        '<h1>UNDE IEȘIM</h1>'
        '<p>Concerte, spectacole, festivaluri și lucruri de făcut în Vâlcea — ordonate după dată și verificate editorial.</p></div>'
        + date_chips + category_chips + empty_note +
        '<section class="event-agenda" id="agenda"><div class="event-agenda-title"><h2>Agenda verificată</h2>'
        f'<span>{len(upcoming)} evenimente disponibile acum</span></div>'
        + ''.join(groups) +
        '</section>'
        '<aside class="event-tip"><strong>Știi un eveniment care lipsește?</strong>'
        '<span>Trimite-ne organizatorul, data și o sursă publică la redactie@valceaclar.ro.</span></aside>'
        '</div>'
    )


product_routes = []
for product in product_nav_order + ['WEEKEND CLAR', 'PAMFLET/SATIRĂ']:
    product_articles = [article for article in articles if article_product(article) == product]
    if not product_articles:
        continue
    path = product_path(product)
    description = PRODUCT_DESCRIPTIONS.get(product, 'Materiale VÂLCEA CLAR selectate editorial.')
    page_body = event_discovery_page() if product == 'UNDE IEȘIM' else archive_page(product, description, product_articles, 'Format editorial')
    write_route(
        path,
        shell(f'{product} — VÂLCEA CLAR', page_body, description, path, 'event-discovery-page' if product == 'UNDE IEȘIM' else ''),
    )
    product_routes.append((path, product_articles))

if events and not any(path == '/unde-iesim/' for path, _ in product_routes):
    event_path = '/unde-iesim/'
    write_route(
        event_path,
        shell('UNDE IEȘIM — VÂLCEA CLAR', event_discovery_page(), PRODUCT_DESCRIPTIONS['UNDE IEȘIM'], event_path, 'event-discovery-page'),
    )
    product_routes.append((event_path, []))

section_routes = []
for section in sections:
    section_articles = [article for article in articles if article.get('section') == section]
    if not section_articles:
        continue
    path = section_path(section)
    title = section.replace('_', ' ').title()
    description = f'Știri și explicații VÂLCEA CLAR din secțiunea {title}.'
    write_route(
        path,
        shell(f'{title} — VÂLCEA CLAR', archive_page(title, description, section_articles, 'Secțiune'), description, path),
    )
    section_routes.append((path, section_articles))


for article in articles:
    canonical_path = '/stiri/' + article['id'] + '/'
    canonical = route_url(canonical_path)
    fb = 'https://www.facebook.com/sharer/sharer.php?u=' + quote(canonical, safe='')
    wa = 'https://wa.me/?text=' + quote(article['headline'] + ' ' + canonical, safe='')
    mail = 'mailto:?subject=' + quote(article['headline']) + '&body=' + quote(canonical)
    paragraphs = ''.join(f'<p>{h(p)}</p>' for p in article['paragraphs'])
    article_media_html = image_html(article, True)
    article_media_block = f'<div class="article-media">{article_media_html}</div>' if article_media_html else ''
    sources = ''.join(
        f'<li><a href="{h(source["url"])}" rel="nofollow noopener">{h(source["name"])}</a></li>'
        for source in article['sources']
    )
    product = article_product(article)
    product_class = product_slug(article)
    body = (
        f'<article class="article article--{h(product_class)}" data-product="{h(product)}">'
        f'<a class="back top-back" href="{u("/stiri/")}">← Ultimele știri</a>'
        f'{product_kicker(article)}'
        f'<h1>{h(article["headline"])}</h1>'
        f'<p class="dek">{h(article["dek"])}</p>{story_meta(article)}'
        f'{product_signpost(article)}'
        '<div class="share-bar" aria-label="Distribuie articolul"><span>Distribuie</span>'
        f'<a href="{h(fb)}" rel="nofollow noopener">Facebook</a>'
        f'<a href="{h(wa)}" rel="nofollow noopener">WhatsApp</a>'
        f'<a href="{h(mail)}">Email</a></div>'
        f'{article_media_block}'
        f'<div class="article-body">{paragraphs}</div>'
        f'<section class="sources"><h2>Surse și documente</h2><p>Materialul este construit pe surse identificabile. Linkurile de mai jos permit verificarea informațiilor.</p><ul>{sources}</ul></section>'
        f'{related_block(article)}'
        f'<a class="back" href="{u("/stiri/")}">← Înapoi la flux</a>'
        '</article>'
    )
    write_route(
        'stiri/' + article['id'],
        shell(article['headline'] + ' — VÂLCEA CLAR', body, article['dek'], canonical_path, f'article-page product-{product_class}'),
    )

about = (
    '<div class="legal article"><div class="kicker">Despre publicație</div><h1>VÂLCEA CLAR</h1>'
    '<p class="dek">VÂLCEA. CLAR. — Ce se întâmplă. Ce știm. Ce contează.</p>'
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
    'User-agent: *\nDisallow: /\n' if PREVIEW else (
        'User-agent: *\nAllow: /\n'
        'Sitemap: https://valceaclar.ro/sitemap.xml\n'
        'Sitemap: https://valceaclar.ro/news-sitemap.xml\n'
    ),
    encoding='utf-8',
)

latest_published = max((parse_dt(article.get('published')) for article in articles if parse_dt(article.get('published'))), default=None)
latest_value = latest_published.isoformat(timespec='seconds') if latest_published else ''

sitemap_entries = [
    ('/', latest_value),
    ('/stiri/', latest_value),
    ('/despre/', ''),
    ('/termeni/', ''),
    ('/confidentialitate/', ''),
]
for path, page_articles in product_routes + section_routes:
    page_dates = [parse_dt(article.get('published')) for article in page_articles]
    page_dates = [value for value in page_dates if value]
    page_lastmod = max(page_dates).isoformat(timespec='seconds') if page_dates else ''
    sitemap_entries.append((path, page_lastmod))
for article in articles:
    sitemap_entries.append((f'/stiri/{article["id"]}/', sitemap_lastmod(article.get('published'))))

seen_paths = set()
unique_entries = []
for path, lastmod in sitemap_entries:
    if path in seen_paths:
        continue
    seen_paths.add(path)
    unique_entries.append((path, lastmod))

sitemap_xml = [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
]
for path, lastmod in unique_entries:
    sitemap_xml.append('<url>')
    sitemap_xml.append(f'<loc>{xh(SITE + path)}</loc>')
    if lastmod:
        sitemap_xml.append(f'<lastmod>{xh(lastmod)}</lastmod>')
    sitemap_xml.append('</url>')
sitemap_xml.append('</urlset>')
(OUT / 'sitemap.xml').write_text(''.join(sitemap_xml), encoding='utf-8')

news_cutoff = latest_published - timedelta(days=2) if latest_published else None
news_articles = [
    article for article in articles
    if parse_dt(article.get('published'))
    and (news_cutoff is None or parse_dt(article.get('published')) >= news_cutoff)
]
news_xml = [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">',
]
for article in news_articles:
    published = sitemap_lastmod(article.get('published'))
    news_xml.extend([
        '<url>',
        f'<loc>{xh(SITE + "/stiri/" + article["id"] + "/")}</loc>',
        '<news:news>',
        '<news:publication><news:name>VÂLCEA CLAR</news:name><news:language>ro</news:language></news:publication>',
        f'<news:publication_date>{xh(published)}</news:publication_date>',
        f'<news:title>{xh(article["headline"])}</news:title>',
        '</news:news>',
        '</url>',
    ])
news_xml.append('</urlset>')
(OUT / 'news-sitemap.xml').write_text(''.join(news_xml), encoding='utf-8')

print(
    f'Built {len(unique_entries)} indexed routes; {len(news_articles)} Google News sitemap stories; '
    f'{len(list((OUT / "media").glob("*.webp")))} local images; base={BASE or "/"}; preview={PREVIEW}.'
)
