#!/usr/bin/env python3
"""Generate deterministic, candidate-only social cards without posting them."""

from pathlib import Path
from urllib.parse import urlparse
import argparse
import hashlib
import html
import json
import re
import shutil
import subprocess
import textwrap

ROOT = Path(__file__).resolve().parents[1]
FORMATS = {
    'feed_portrait': (1080, 1350),
    'story_vertical': (1080, 1920),
}
VERIFIED_AUTHORITY = 'OWNER_APPROVED_AUTO_PUBLICATION'


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def safe_slug(value):
    value = str(value).lower().translate(str.maketrans('ăâîșşțţ', 'aaiss tt'.replace(' ', '')))
    value = re.sub(r'[^a-z0-9]+', '-', value).strip('-')
    return value[:80] or 'card'


def is_https(value):
    parsed = urlparse(str(value))
    return parsed.scheme == 'https' and bool(parsed.netloc)


def verified_articles(payload):
    result = []
    for article in payload.get('articles', []):
        automation = article.get('automation') or {}
        sources = article.get('sources') or []
        if (
            article.get('publication_mode') == 'AUTO_PUBLISHED'
            and automation.get('authority') == VERIFIED_AUTHORITY
            and automation.get('source_tier') == 'T1'
            and article.get('published')
            and sources
            and all(is_https(source.get('url')) for source in sources)
        ):
            result.append(article)
    return result


def article_card(article):
    source = article['sources'][0]
    return {
        'id': 'article-' + safe_slug(article['id']),
        'state': 'PUBLISHED_VERIFIED',
        'state_label': 'PUBLICAT · VERIFICAT T1',
        'section': article.get('section', 'ȘTIRI'),
        'headline': article['headline'],
        'detail': article.get('dek', ''),
        'source_name': source['name'],
        'source_url': source['url'],
        'canonical_url': f'https://valceaclar.ro/stiri/{article["id"]}/',
    }


def candidate_cards(brief):
    if brief.get('status') != 'candidate_only' or brief.get('product_id') != 'tomorrow_locality_brief':
        return []
    target = brief.get('target_date') or 'dată neconfirmată'
    result = []
    for locality in brief.get('localities', []):
        uat = locality.get('uat')
        for index, alert in enumerate(locality.get('alerts', []), start=1):
            source_url = alert.get('source_url')
            if not uat or not is_https(source_url):
                continue
            start = str(alert.get('valid_from', ''))[11:16]
            end = str(alert.get('valid_until', ''))[11:16]
            result.append({
                'id': f'utility-{safe_slug(uat)}-{index}',
                'state': 'CANDIDATE_ONLY',
                'state_label': 'CANDIDAT · NU ESTE ȘTIRE PUBLICATĂ',
                'section': 'UTILITĂȚI · MÂINE ÎN LOCALITATEA TA',
                'headline': f'{uat}: întrerupere programată de electricitate',
                'detail': f'{target} · {start}–{end} · {alert.get("zone", "zonă nespecificată")}',
                'source_name': 'Distribuție Oltenia — calendar oficial',
                'source_url': source_url,
                'canonical_url': None,
            })
    return result


def text_lines(value, width):
    return textwrap.wrap(str(value), width=width, break_long_words=False, break_on_hyphens=False) or ['']


def svg_text(lines, x, y, size, weight='400', fill='#111111', leading=1.18):
    tspans = []
    for index, line in enumerate(lines):
        dy = 0 if index == 0 else round(size * leading)
        tspans.append(f'<tspan x="{x}" dy="{dy}">{html.escape(line)}</tspan>')
    return f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{fill}">' + ''.join(tspans) + '</text>'


def render_svg(card, width, height):
    margin = 76
    headline_size = 68 if height < 1600 else 76
    detail_size = 31 if height < 1600 else 36
    headline_width = 22 if height < 1600 else 19
    detail_width = 47 if height < 1600 else 42
    state_fill = '#fff0ed' if card['state'] == 'CANDIDATE_ONLY' else '#edf7ef'
    state_ink = '#8f1d14' if card['state'] == 'CANDIDATE_ONLY' else '#1d6234'
    headline = text_lines(card['headline'], headline_width)[:6]
    detail = text_lines(card['detail'], detail_width)[:5]
    source = text_lines('SURSĂ: ' + card['source_name'], 58)[:3]
    headline_y = 420 if height < 1600 else 530
    detail_y = headline_y + len(headline) * round(headline_size * 1.18) + 68
    source_y = height - 205
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<rect width="{width}" height="{height}" fill="#f7f5ef"/>
<rect x="0" y="0" width="{width}" height="24" fill="#b42318"/>
<style>text{{font-family:"DejaVu Sans",Arial,sans-serif}}</style>
<text x="{margin}" y="112" font-size="55" font-weight="800" letter-spacing="-2" fill="#111111">VÂLCEA CLAR</text>
<text x="{width-margin}" y="108" text-anchor="end" font-size="20" font-weight="700" letter-spacing="2" fill="#666666">FAPTE · DOCUMENTE · CONTEXT</text>
<line x1="{margin}" y1="154" x2="{width-margin}" y2="154" stroke="#111111" stroke-width="3"/>
<rect x="{margin}" y="202" width="{width-2*margin}" height="82" rx="8" fill="{state_fill}" stroke="{state_ink}" stroke-width="2"/>
<text x="{margin+25}" y="254" font-size="25" font-weight="800" letter-spacing="1" fill="{state_ink}">{html.escape(card['state_label'])}</text>
<text x="{margin}" y="350" font-size="24" font-weight="800" letter-spacing="2" fill="#b42318">{html.escape(card['section'].upper())}</text>
{svg_text(headline, margin, headline_y, headline_size, '800')}
{svg_text(detail, margin, detail_y, detail_size, '400', '#414141', 1.35)}
<line x1="{margin}" y1="{source_y-52}" x2="{width-margin}" y2="{source_y-52}" stroke="#999999" stroke-width="2"/>
{svg_text(source, margin, source_y, 23, '700', '#333333', 1.25)}
<text x="{margin}" y="{height-70}" font-size="20" font-weight="700" letter-spacing="1" fill="#666666">VALCEACLAR.RO · VERIFICĂ SURSA ÎNAINTE DE DISTRIBUIRE</text>
</svg>'''


def render_png(card, width, height, png_path):
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return False
    regular = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    bold = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
    if not Path(regular).exists() or not Path(bold).exists():
        return False
    image = Image.new('RGB', (width, height), '#f7f5ef')
    draw = ImageDraw.Draw(image)
    margin = 76
    headline_size = 68 if height < 1600 else 76
    detail_size = 31 if height < 1600 else 36
    state_fill = '#fff0ed' if card['state'] == 'CANDIDATE_ONLY' else '#edf7ef'
    state_ink = '#8f1d14' if card['state'] == 'CANDIDATE_ONLY' else '#1d6234'
    fonts = {
        'brand': ImageFont.truetype(bold, 55),
        'tag': ImageFont.truetype(bold, 20),
        'state': ImageFont.truetype(bold, 25),
        'section': ImageFont.truetype(bold, 24),
        'headline': ImageFont.truetype(bold, headline_size),
        'detail': ImageFont.truetype(regular, detail_size),
        'source': ImageFont.truetype(bold, 23),
        'footer': ImageFont.truetype(bold, 20),
    }
    def pixel_lines(value, font, max_width, max_lines):
        lines = []
        current = ''
        for word in str(value).split():
            proposal = f'{current} {word}'.strip()
            if current and draw.textlength(proposal, font=font) > max_width:
                lines.append(current)
                current = word
            else:
                current = proposal
        if current:
            lines.append(current)
        return lines[:max_lines] or ['']
    draw.rectangle((0, 0, width, 24), fill='#b42318')
    draw.text((margin, 61), 'VÂLCEA CLAR', font=fonts['brand'], fill='#111111')
    tag = 'FAPTE · DOCUMENTE · CONTEXT'
    tag_box = draw.textbbox((0, 0), tag, font=fonts['tag'])
    draw.text((width - margin - (tag_box[2] - tag_box[0]), 78), tag, font=fonts['tag'], fill='#666666')
    draw.line((margin, 154, width - margin, 154), fill='#111111', width=3)
    draw.rounded_rectangle((margin, 202, width - margin, 284), radius=8, fill=state_fill, outline=state_ink, width=2)
    draw.text((margin + 25, 227), card['state_label'], font=fonts['state'], fill=state_ink)
    draw.text((margin, 322), card['section'].upper(), font=fonts['section'], fill='#b42318')

    headline_y = 400 if height < 1600 else 510
    for line in pixel_lines(card['headline'], fonts['headline'], width - 2 * margin, 6):
        draw.text((margin, headline_y), line, font=fonts['headline'], fill='#111111')
        headline_y += round(headline_size * 1.18)
    detail_y = headline_y + 42
    for line in pixel_lines(card['detail'], fonts['detail'], width - 2 * margin, 5):
        draw.text((margin, detail_y), line, font=fonts['detail'], fill='#414141')
        detail_y += round(detail_size * 1.35)

    source_y = height - 205
    draw.line((margin, source_y - 52, width - margin, source_y - 52), fill='#999999', width=2)
    for line in pixel_lines('SURSĂ: ' + card['source_name'], fonts['source'], width - 2 * margin, 3):
        draw.text((margin, source_y - 22), line, font=fonts['source'], fill='#333333')
        source_y += round(23 * 1.25)
    draw.text((margin, height - 92), 'VALCEACLAR.RO · VERIFICĂ SURSA ÎNAINTE DE DISTRIBUIRE', font=fonts['footer'], fill='#666666')
    image.save(png_path, 'PNG', optimize=False, compress_level=9)
    return png_path.exists()


def convert_png(card, width, height, svg_path, png_path):
    if render_png(card, width, height, png_path):
        return True
    converter = shutil.which('convert')
    if not converter:
        return False
    result = subprocess.run([converter, '-background', 'none', str(svg_path), str(png_path)], capture_output=True)
    return result.returncode == 0 and png_path.exists()


def build_cards(articles, brief, output, make_png=True):
    output = Path(output)
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    source_cards = [article_card(article) for article in verified_articles(articles)] + candidate_cards(brief)
    generated = []
    for card in source_cards:
        for format_id, (width, height) in FORMATS.items():
            stem = f'{card["id"]}-{format_id}'
            svg_path = output / f'{stem}.svg'
            svg = render_svg(card, width, height)
            svg_path.write_text(svg, encoding='utf-8')
            png_name = None
            if make_png:
                png_path = output / f'{stem}.png'
                if convert_png(card, width, height, svg_path, png_path):
                    png_name = png_path.name
            generated.append({
                'card_id': card['id'],
                'format': format_id,
                'width': width,
                'height': height,
                'state': card['state'],
                'svg': svg_path.name,
                'png': png_name,
                'source_name': card['source_name'],
                'source_url': card['source_url'],
                'canonical_url': card['canonical_url'],
                'sha256': hashlib.sha256(svg.encode('utf-8')).hexdigest(),
            })
    manifest = {
        'schema_version': 1,
        'status': 'CANDIDATE_NO_POST',
        'auto_post': False,
        'verified_published_inputs': len(verified_articles(articles)),
        'candidate_utility_inputs': len(candidate_cards(brief)),
        'cards': generated,
    }
    (output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--articles', default=ROOT / 'content' / 'articles.json')
    parser.add_argument('--brief', default=ROOT / 'newsroom' / 'output' / 'locality_brief.json')
    parser.add_argument('--output', default=ROOT / 'newsroom' / 'output' / 'social_cards')
    parser.add_argument('--svg-only', action='store_true')
    args = parser.parse_args()
    brief_path = Path(args.brief)
    brief = load(brief_path) if brief_path.exists() else {'status': 'candidate_only', 'product_id': 'tomorrow_locality_brief', 'localities': []}
    manifest = build_cards(load(args.articles), brief, args.output, make_png=not args.svg_only)
    print(f'SOCIAL CARDS PASS: {len(manifest["cards"])} variants; status={manifest["status"]}; auto_post=false.')


if __name__ == '__main__':
    main()
