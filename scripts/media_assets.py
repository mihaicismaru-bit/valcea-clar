from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import base64
import hashlib
import ipaddress
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'media_source'
CONTENT = ROOT / 'content'
MAX_REMOTE_BYTES = 12 * 1024 * 1024
UA = 'VÂLCEA-CLAR-Public-Media-Mirror/1.0 (+https://valceaclar.ro/)'


def _local_manifest() -> dict:
    return json.loads((SRC / 'manifest.json').read_text(encoding='utf-8'))


def _canonical_articles() -> list[dict]:
    path = CONTENT / 'articles.json'
    if not path.is_file():
        return []
    doc = json.loads(path.read_text(encoding='utf-8'))
    return [row for row in doc.get('articles', []) if isinstance(row, dict)]


def _safe_remote_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme != 'https' or not parsed.hostname:
        raise ValueError('media mirror requires https URL')
    host = parsed.hostname.lower().strip('.')
    if host == 'localhost' or host.endswith('.local'):
        raise ValueError('media mirror refuses local host')
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    if ip and (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved):
        raise ValueError('media mirror refuses non-public IP')
    return value


def _looks_like_image(data: bytes) -> bool:
    return (
        data.startswith(b'\xff\xd8\xff')
        or data.startswith(b'\x89PNG\r\n\x1a\n')
        or (len(data) >= 12 and data[:4] == b'RIFF' and data[8:12] == b'WEBP')
    )


def _download_image(url: str) -> tuple[bytes, str]:
    _safe_remote_url(url)
    req = Request(
        url,
        headers={
            'User-Agent': UA,
            'Accept': 'image/avif,image/webp,image/png,image/jpeg,image/*;q=0.8,*/*;q=0.1',
            'Cache-Control': 'no-cache',
        },
    )
    with urlopen(req, timeout=45) as response:
        final_url = response.geturl()
        _safe_remote_url(final_url)
        content_type = (response.headers.get('content-type') or '').lower()
        data = response.read(MAX_REMOTE_BYTES + 1)
    if len(data) > MAX_REMOTE_BYTES:
        raise ValueError('media mirror exceeds size cap')
    if not data or (not content_type.startswith('image/') and not _looks_like_image(data)):
        raise ValueError(f'media mirror is not an image: {content_type or "unknown"}')
    if not _looks_like_image(data):
        raise ValueError('media mirror image signature is unsupported')
    return data, final_url


def materialize_media(target: Path, articles: list[dict] | None = None) -> set[str]:
    """Build local media and mirror verified canonical CIVORA visuals.

    Curated media committed in ``media_source`` is deterministic and mandatory.
    CIVORA visuals are canonical provenance records but their network transfer is
    best-effort: a transient remote image failure must not stop publication of the
    verified article itself. Missing mirrors stay visible to the independent
    public-media health gate.
    """
    target.mkdir(parents=True, exist_ok=True)
    if articles is None:
        articles = _canonical_articles()
    available: set[str] = set()
    provenance: dict[str, dict] = {}

    for name, spec in _local_manifest().items():
        data = base64.b64decode((SRC / (name + '.b64')).read_text(encoding='utf-8').strip())
        if len(data) != spec['size'] or hashlib.sha256(data).hexdigest() != spec['sha256']:
            raise ValueError('media hash mismatch: ' + name)
        (target / name).write_bytes(data)
        available.add(name)
        provenance[name] = {
            'delivery': 'committed_curated_asset',
            'sha256': hashlib.sha256(data).hexdigest(),
            'bytes': len(data),
        }

    mirrors: dict[str, dict] = {}
    for article in articles:
        name = str(article.get('image') or '').strip()
        fetch_url = str(article.get('image_fetch_url') or '').strip()
        if not name or not fetch_url:
            continue
        if Path(name).name != name:
            raise ValueError('unsafe media filename: ' + name)
        spec = {
            'fetch_url': fetch_url,
            'origin_url': str(article.get('image_origin_url') or fetch_url),
            'source_url': str(article.get('image_source_url') or ''),
            'credit': str(article.get('image_credit') or ''),
            'rights_basis': str(article.get('image_rights_basis') or ''),
            'license_url': str(article.get('image_license_url') or ''),
            'provenance_status': str(article.get('image_provenance_status') or ''),
        }
        incumbent = mirrors.get(name)
        if incumbent and incumbent['fetch_url'] != fetch_url:
            raise ValueError('conflicting canonical media mirror filename: ' + name)
        mirrors[name] = spec

    failures = []
    mirrored = 0
    for name, spec in mirrors.items():
        if name in available:
            continue
        if spec['provenance_status'] != 'VERIFIED':
            continue
        try:
            data, final_url = _download_image(spec['fetch_url'])
        except Exception as exc:
            failures.append({'file': name, 'url': spec['fetch_url'], 'error': f'{type(exc).__name__}: {exc}'})
            continue
        (target / name).write_bytes(data)
        available.add(name)
        mirrored += 1
        provenance[name] = {
            **spec,
            'delivery': 'civora_verified_build_mirror',
            'final_fetch_url': final_url,
            'sha256': hashlib.sha256(data).hexdigest(),
            'bytes': len(data),
        }

    (target / 'provenance.json').write_text(
        json.dumps(
            {
                'schema_version': '1.0',
                'assets': provenance,
                'mirror_failures': failures,
            },
            ensure_ascii=False,
            indent=2,
        ) + '\n',
        encoding='utf-8',
    )
    print(
        f'MEDIA MATERIALIZE: available={len(available)} canonical_mirrored={mirrored} failures={len(failures)}',
        file=sys.stderr if failures else sys.stdout,
    )
    for row in failures:
        print(f"MEDIA MIRROR HOLD: {row['file']} {row['error']}", file=sys.stderr)
    return available


def read_media(name):
    manifest = _local_manifest()
    spec = manifest[name]
    data = base64.b64decode((SRC / (name + '.b64')).read_text(encoding='utf-8').strip())
    if hashlib.sha256(data).hexdigest() != spec['sha256']:
        raise ValueError('media hash mismatch: ' + name)
    return data
