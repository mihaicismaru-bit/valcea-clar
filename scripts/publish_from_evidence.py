"""Prepare a reviewed story for the existing Pages pipeline from a NAS snapshot.

This does not fetch credentials, push to GitHub, or claim semantic fact checking.
Each paragraph carries a source excerpt for an editor to check. The original blob
is verified against the collector's digest before the projection is written.
"""
from __future__ import annotations

import argparse
import hashlib
from html.parser import HTMLParser
import json
import re
import sqlite3
from pathlib import Path
from urllib.parse import urlsplit


def under(root: Path, name: str) -> Path:
    result = (root / name).resolve()
    if not result.is_relative_to(root):
        raise ValueError('evidence path is outside snapshot')
    return result


def normalize(text: str) -> str:
    return ' '.join(text.split()).casefold()


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.excluded = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style', 'head', 'nav', 'footer', 'header', 'aside'}:
            self.excluded += 1

    def handle_endtag(self, tag):
        if tag in {'script', 'style', 'head', 'nav', 'footer', 'header', 'aside'} and self.excluded:
            self.excluded -= 1

    def handle_data(self, data):
        if not self.excluded:
            self.parts.append(data)


def prepare(snapshot: Path, projection: Path, reviewed: Path, output: Path):
    root = snapshot.resolve()
    dbpath = root / 'evidence.sqlite'
    if not dbpath.is_file():
        raise ValueError('evidence.sqlite missing')
    wal = Path(str(dbpath) + '-wal')
    if wal.exists() and wal.stat().st_size:
        raise ValueError('snapshot has an uncheckpointed WAL')
    item = json.loads(reviewed.read_text(encoding='utf-8'))
    url = item['source_url']
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname not in {'primariavl.ro', 'www.primariavl.ro', 'dm.primariavl.ro'}:
        raise ValueError('source must be an official municipal HTTPS URL')
    if item.get('editorially_verified') is not True:
        raise ValueError('article needs editorial verification')
    db = sqlite3.connect(dbpath.as_uri() + '?mode=ro&immutable=1', uri=True)
    db.row_factory = sqlite3.Row
    try:
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('database integrity check failed')
        row = db.execute('SELECT sha,blob_path,text_path,content_type,extraction_status FROM versions WHERE url=? AND sha=?', (url, item['source_sha256'])).fetchone()
    finally:
        db.close()
    if not row or row['extraction_status'] != 'EXTRACTED':
        raise ValueError('reviewed version not present in collector snapshot')
    blob = under(root, row['blob_path']).read_bytes()
    if hashlib.sha256(blob).hexdigest() != row['sha']:
        raise ValueError('source hash mismatch')
    content_type = str(row['content_type'] or '').lower()
    if 'html' not in content_type:
        raise ValueError('only HTML evidence can currently be rechecked against its original blob')
    match = re.search(r'charset=([^;\s]+)', content_type)
    try:
        html = blob.decode(match.group(1).strip('"\'') if match else 'utf-8')
    except (UnicodeDecodeError, LookupError):
        html = blob.decode('cp1250', errors='replace')
    parser = VisibleText()
    parser.feed(html)
    source = normalize(' '.join(parser.parts))
    extracted = normalize(under(root, row['text_path']).read_text(encoding='utf-8'))
    paragraphs = item['paragraphs']
    if not paragraphs or any(not p.get('text', '').strip() or len(normalize(p.get('source_excerpt', ''))) < 20 or normalize(p['source_excerpt']) not in source or normalize(p['source_excerpt']) not in extracted for p in paragraphs):
        raise ValueError('each paragraph needs an excerpt present in collected text')
    story_id = item['id']
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', story_id):
        raise ValueError('invalid article id')
    document = json.loads(projection.read_text(encoding='utf-8'))
    articles = document['articles']
    existing = next((x for x in articles if x.get('id') == story_id), None)
    if existing:
        if existing.get('evidence_sha256') == row['sha']:
            return 'already-present'
        raise ValueError('article id already exists with a different source version')
    if any(x.get('evidence_sha256') == row['sha'] for x in articles):
        raise ValueError('source version is already used by another article')
    story = {'id': story_id, 'section': item['section'], 'priority': item.get('priority', 2000001),
             'headline': item['headline'], 'dek': item['dek'],
             'paragraphs': [p['text'] for p in paragraphs],
             'sources': [{'name': 'Primăria Râmnicu Vâlcea', 'url': url, 'tier': 'T1'}],
             'published': item['published'], 'image': None, 'canonical_source': 'VÂLCEA CLAR',
             'canonical_path': '/stiri/' + story_id + '/', 'editorial_product': item.get('editorial_product', 'service_news'),
             'archive_only': False, 'active_now': True, 'archive_status': 'active', 'evidence_sha256': row['sha']}
    articles.insert(0, story)
    document['current_story_ids'] = [story_id] + [i for i in document.get('current_story_ids', []) if i != story_id]
    document['updated_local'] = item['published']
    if output.resolve() == projection.resolve():
        raise ValueError('output must not overwrite the input projection')
    output.write_text(json.dumps(document, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return 'prepared'


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--snapshot', type=Path, required=True)
    p.add_argument('--projection', type=Path, required=True)
    p.add_argument('--reviewed', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    print(prepare(a.snapshot, a.projection, a.reviewed, a.output))
