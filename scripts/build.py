#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime
from urllib.parse import quote
import html
import json
import os
import shutil

from media_assets import materialize_media
from trust import corrections_for, validate_contract, verification_state

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '_site'
C = ROOT / 'content'
STRATEGY = ROOT / 'strategy'
NEWSROOM_OUT = ROOT / 'newsroom' / 'output'
BASE = os.getenv('VALCEA_CLAR_BASE_PATH', '').rstrip('/')
PREVIEW = os.getenv('VALCEA_CLAR_PREVIEW', '') == '1'
SITE = 'https://valceaclar.ro'


def load(name):
    return json.loads((C / name).read_text(encoding='utf-8'))


def load_strategy(name):
    return json.loads((STRATEGY / name).read_text(encoding='utf-8'))


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
corrections = load('corrections.json')
trust_contract = load_strategy('trust_transparency_contract.json')
trust_errors = validate_contract(trust_contract, corrections, {article['id'] for article in articles})
if trust_errors:
    raise ValueError('Invalid trust/transparency contract: ' + ', '.join(trust_errors))
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
    f'<a href="{u("/standarde/")}">Standarde</a>'
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


def shell(title, body, desc='Știri locale verificate din Vâlcea.', canonical_path='/', body_class='', og_type='website', og_image=None, extra_head='', robots_override=None):
    robots_value = robots_override or ('noindex,nofollow' if PREVIEW else 'max-image-preview:large')
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
  <div class="footer-links"><a href="{u('/despre/')}">Despre</a> · <a href="{u('/standarde/')}">Standarde</a> · <a href="{u('/corectii/')}">Corecții</a> · <a href="{u('/termeni/')}">Termeni</a> · <a href="{u('/confidentialitate/')}">Confidențialitate</a></div>
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


def load_candidate_locality_brief():
    path = NEWSROOM_OUT / 'locality_brief.json'
    if not path.exists():
        return {'status': 'candidate_only', 'target_date': None, 'localities': []}
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return {'status': 'candidate_only', 'target_date': None, 'localities': []}
    if data.get('status') != 'candidate_only' or data.get('product_id') != 'tomorrow_locality_brief':
        return {'status': 'candidate_only', 'target_date': None, 'localities': []}
    return data


coverage = json.loads((STRATEGY / 'source_coverage_matrix.json').read_text(encoding='utf-8'))
uats = coverage.get('uats', [])
brief = load_candidate_locality_brief()
brief_by_uat = {item.get('uat'): item.get('alerts', []) for item in brief.get('localities', [])}
uat_options = ''.join(
    f'<option value="{h(item["name"])}" data-uat-type="{h(item.get("type", ""))}">{h(item["name"])}</option>'
    for item in uats
)
alert_groups = ''
for item in uats:
    uat = item['name']
    alerts = brief_by_uat.get(uat, [])
    cards = ''
    for alert in alerts:
        source_url = str(alert.get('source_url', ''))
        if not source_url.startswith('https://'):
            continue
        utility = 'Electricitate' if alert.get('utility') == 'electricity' else 'Utilitate locală'
        start = pretty_date(alert.get('valid_from'))
        end = pretty_date(alert.get('valid_until'))
        cards += (
            '<article class="utility-alert">'
            f'<div class="kicker">{h(utility)} · candidate_only</div>'
            f'<h3>{h(start)} – {h(end)}</h3>'
            f'<p>{h(alert.get("zone", "Zonă nespecificată"))}</p>'
            f'<a href="{h(source_url)}" rel="nofollow noopener">Documentul oficial al operatorului →</a>'
            '</article>'
        )
    alert_groups += (
        f'<section class="utility-results" data-uat="{h(uat)}" hidden>'
        + (cards or '<div class="utility-empty">Nu există alerte candidate structurate pentru această localitate în fereastra curentă.</div>')
        + '</section>'
    )

utility_script = '''<script>
(() => {
  const key = 'vc_locality_session_v1';
  const select = document.querySelector('#saved-locality');
  const prompt = document.querySelector('#locality-prompt');
  const groups = [...document.querySelectorAll('[data-uat]')];
  const show = (name) => {
    groups.forEach((group) => { group.hidden = group.dataset.uat !== name; });
    prompt.hidden = Boolean(name);
  };
  const saved = sessionStorage.getItem(key) || '';
  if ([...select.options].some((option) => option.value === saved)) select.value = saved;
  show(select.value);
  select.addEventListener('change', () => {
    sessionStorage.setItem(key, select.value);
    show(select.value);
  });
})();
</script>'''
utility_body = (
    '<div class="utility-page">'
    '<div class="candidate-banner"><strong>Instrument în test</strong><span>Conținut candidate_only · nu este o știre publicată și nu declanșează alerte.</span></div>'
    '<div class="eyebrow">Utilitate locală</div><h1 class="page-title">Mâine în localitatea ta</h1>'
    '<p class="page-dek">Alege o localitate pentru a vedea întreruperile programate detectate în surse oficiale. Preferința este păstrată numai în această sesiune; nu creăm un identificator persistent.</p>'
    '<div class="locality-picker"><label for="saved-locality">Localitatea mea</label>'
    f'<select id="saved-locality"><option value="">Alege una dintre cele {len(uats)} de localități</option>{uat_options}</select>'
    '<p class="privacy-note">Datele sunt candidate și pot fi incomplete. Verifică documentul oficial înainte de a lua o decizie.</p></div>'
    '<div id="locality-prompt" class="utility-empty">Selectează localitatea pentru rezultatele disponibile.</div>'
    f'{alert_groups}{utility_script}</div>'
)
write_route(
    'instrumente/maine-in-localitatea-ta',
    shell(
        'Mâine în localitatea ta — instrument în test — VÂLCEA CLAR',
        utility_body,
        'View candidat pentru alerte oficiale de utilități, filtrat pe localitate.',
        '/instrumente/maine-in-localitatea-ta/',
        'utility-candidate-page',
        robots_override='noindex,nofollow',
    ),
)

for article in articles:
    canonical_path = '/stiri/' + article['id'] + '/'
    canonical = route_url(canonical_path)
    canonical_image = canonical_article_image(article)
    published = article.get('published', '')
    modified = article.get('updated') or published
    verification = verification_state(article, trust_contract)
    verification_json = json.dumps(verification, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')
    article_head = (
        f'<meta property="article:published_time" content="{h(published)}">\n'
        f'<meta property="article:modified_time" content="{h(modified)}">\n'
        f'<script type="application/ld+json">{news_article_schema(article, canonical, canonical_image)}</script>\n'
        f'<script type="application/json" id="editorial-verification">{verification_json}</script>'
    )
    fb = 'https://www.facebook.com/sharer/sharer.php?u=' + quote(canonical, safe='')
    wa = 'https://wa.me/?text=' + quote(article['headline'] + ' ' + canonical, safe='')
    mail = 'mailto:?subject=' + quote(article['headline']) + '&body=' + quote(canonical)
    paragraphs = ''.join(f'<p>{h(p)}</p>' for p in article['paragraphs'])
    sources = ''.join(
        f'<li><a href="{h(source["url"])}" rel="nofollow noopener">{h(source["name"])}</a></li>'
        for source in article['sources']
    )
    article_corrections = corrections_for(article['id'], corrections)
    if article_corrections:
        correction_items = ''.join(
            f'<li><time datetime="{h(item["published_local"])}">{h(pretty_date(item["published_local"]))}</time> — {h(item["summary"])}</li>'
            for item in article_corrections
        )
        corrections_block = f'<section class="article-corrections"><h2>Corecții și clarificări</h2><ul>{correction_items}</ul></section>'
    else:
        corrections_block = ''
    verified = verification['distribution_eligible_as_verified']
    verification_note = (
        'Metadatele de publicare, autoritatea și sursa T1 îndeplinesc contractul public de verificare.'
        if verified else
        'Această stare nu declară materialul fals. Metadatele complete de verificare lipsesc, iar articolul este exclus din distribuția etichetată „verificat” până la o revizuire documentată.'
    )
    verification_block = (
        '<section class="verification-panel" aria-label="Starea verificării">'
        f'<div class="verification-badge {"verified" if verified else "legacy"}">{h(verification["label"])}</div>'
        f'<p>{h(verification_note)} <a href="{u("/standarde/")}">Cum derivăm această stare</a>.</p>'
        '</section>'
    )
    body = (
        '<article class="article">'
        f'<a class="back top-back" href="{u("/stiri/")}">← Ultimele știri</a>'
        f'<div class="kicker">{h(article["section"])}</div>'
        f'<h1>{h(article["headline"])}</h1>'
        f'<p class="dek">{h(article["dek"])}</p>{story_meta(article)}'
        f'{verification_block}'
        '<div class="share-bar" aria-label="Distribuie articolul"><span>Distribuie</span>'
        f'<a href="{h(fb)}" rel="nofollow noopener">Facebook</a>'
        f'<a href="{h(wa)}" rel="nofollow noopener">WhatsApp</a>'
        f'<a href="{h(mail)}">Email</a></div>'
        f'<div class="article-media">{image_html(article, True)}</div>'
        f'<div class="article-body">{paragraphs}</div>'
        f'<section class="sources"><h2>Surse și documente</h2><p>Materialul este construit pe surse identificabile. Linkurile de mai jos permit verificarea informațiilor.</p><ul>{sources}</ul></section>'
        f'{corrections_block}'
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

ownership = trust_contract['ownership_disclosure']
standards = (
    '<div class="legal article"><div class="kicker">Transparență editorială</div><h1>Cum verificăm</h1>'
    '<p class="dek">Etichetele de verificare sunt derivate din metadate și surse, nu adăugate discreționar de generatorul site-ului.</p>'
    '<section><h2>Publicat · verificat T1</h2><p>Eticheta apare numai când articolul este publicat prin autoritatea aprobată, are nivel T1 și cel puțin o sursă HTTPS identificabilă. Aceste condiții sunt verificate automat și nu garantează că informația nu va necesita ulterior o corecție.</p></section>'
    '<section><h2>Materiale cu metadate incomplete</h2><p>Materialele publicate anterior contractului pot avea surse bune, dar rămân excluse fail-closed din distribuția etichetată „verificat” până la o revizuire editorială documentată. Eticheta nu înseamnă că articolul este fals.</p></section>'
    '<section><h2>Corecții</h2><p>Erorile materiale confirmate sunt corectate în articol și înscrise în registrul public cu data și descrierea schimbării. Semnalările pot fi trimise la redactie@valceaclar.ro. <a href="' + u('/corectii/') + '">Vezi registrul corecțiilor</a>.</p></section>'
    '<section><h2>Responsabilitate editorială și proprietate</h2><p>Responsabilitatea editorială publică este indicată ca ' + h(ownership['editorial_responsibility']) + '. Identitatea entității juridice editoare nu este încă declarată în datele canonice; nu o completăm prin presupunere. Această pagină va fi actualizată după confirmarea ownerului.</p></section>'
    '<section><h2>Ce nu schimbă acest contract</h2><p>Contractul nu extinde lista surselor autorizate, dreptul de publicare automată, expedierea pe canale directe sau auto-postarea socială.</p></section></div>'
)
write_route('standarde', shell('Cum verificăm — VÂLCEA CLAR', standards, 'Standardele publice de verificare, surse, corecții și responsabilitate editorială.', '/standarde/'))

if corrections['entries']:
    registry_items = ''.join(
        '<section><h2><a href="' + u('/stiri/' + h(item['article_id']) + '/') + '">' + h(item['article_id']) + '</a></h2>'
        '<p><time datetime="' + h(item['published_local']) + '">' + h(pretty_date(item['published_local'])) + '</time> · ' + h(item['kind']) + '</p>'
        '<p>' + h(item['summary']) + '</p></section>'
        for item in corrections['entries']
    )
else:
    registry_items = '<section><h2>Nicio intrare în perioada acoperită</h2><p>Registrul este gol de la data începerii lui. Acest lucru nu dovedește că nu au existat corecții anterior și nu înlocuiește istoricul vizibil al fiecărui articol.</p></section>'
corrections_body = (
    '<div class="legal article"><div class="kicker">Transparență editorială</div><h1>Corecții și clarificări</h1>'
    '<p class="dek">Registru public al schimbărilor materiale făcute după publicare.</p>'
    '<p class="registry-scope">Registrul a început la ' + h(pretty_date(corrections['registry_started_local'])) + '. Pentru o semnalare: redactie@valceaclar.ro.</p>'
    + registry_items + '</div>'
)
write_route('corectii', shell('Corecții și clarificări — VÂLCEA CLAR', corrections_body, 'Registrul public al corecțiilor și clarificărilor VÂLCEA CLAR.', '/corectii/'))

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
urls = ['/', '/stiri/', '/despre/', '/standarde/', '/corectii/', '/termeni/', '/confidentialitate/'] + [f'/stiri/{a["id"]}/' for a in articles]
(OUT / 'sitemap.xml').write_text(
    '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    + ''.join(f'<url><loc>{SITE}{path}</loc></url>' for path in urls)
    + '</urlset>',
    encoding='utf-8',
)
print(f'Built {len(urls)} routes; {len(list((OUT / "media").glob("*.webp")))} local images; base={BASE or "/"}; preview={PREVIEW}.')
