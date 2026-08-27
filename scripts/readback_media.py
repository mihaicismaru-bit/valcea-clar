#!/usr/bin/env python3
"""Verify that canonical verified CIVORA visuals are actually live on valceaclar.ro.

This is an observability/readback probe, not an editorial authority. It accepts only
visuals already projected from CIVORA with `image_provenance_status=VERIFIED`, then
requires the public article to reference the expected local mirror, the mirror to
return an image, and public media provenance to map that mirror back to the exact
canonical CIVORA visual origin.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
ARTICLES = ROOT / "content" / "articles.json"
SITE = "https://valceaclar.ro"
UA = "VÂLCEA-CLAR-Live-Media-Readback/1.0 (+https://valceaclar.ro/)"


def _get(url: str, accept: str = "*/*") -> tuple[bytes, str]:
    req = Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": accept,
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
    )
    with urlopen(req, timeout=30) as response:
        return response.read(), (response.headers.get("content-type") or "").lower()


def _looks_like_image(data: bytes) -> bool:
    return (
        data.startswith(b"\xff\xd8\xff")
        or data.startswith(b"\x89PNG\r\n\x1a\n")
        or (len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP")
    )


def main() -> int:
    doc = json.loads(ARTICLES.read_text(encoding="utf-8"))
    expected = [
        row for row in doc.get("articles", [])
        if row.get("image_provenance_status") == "VERIFIED" and row.get("image")
    ]
    if not expected:
        raise SystemExit("LIVE MEDIA READBACK FAIL: no verified canonical visuals in public projection")

    nonce = int(time.time())
    provenance_bytes, provenance_type = _get(
        f"{SITE}/media/provenance.json?readback={nonce}",
        "application/json,*/*;q=0.1",
    )
    if "json" not in provenance_type:
        raise SystemExit(f"LIVE MEDIA READBACK FAIL: provenance content-type={provenance_type or 'missing'}")
    provenance = json.loads(provenance_bytes.decode("utf-8"))
    if provenance.get("mirror_failures"):
        raise SystemExit(f"LIVE MEDIA READBACK FAIL: deployed mirror failures={provenance['mirror_failures']}")
    assets = provenance.get("assets") or {}

    failures = []
    checked_files: set[str] = set()
    for article in expected:
        story_id = str(article["id"])
        image = str(article["image"])
        expected_origin = str(article.get("image_origin_url") or "")
        try:
            html_bytes, content_type = _get(
                f"{SITE}/stiri/{quote(story_id, safe='')}/?media_readback={nonce}",
                "text/html,*/*;q=0.1",
            )
            if "text/html" not in content_type:
                raise ValueError(f"article content-type={content_type or 'missing'}")
            page = html_bytes.decode("utf-8", "replace")
            local_ref = f"/media/{image}"
            if local_ref not in page:
                raise ValueError(f"article missing local image ref {local_ref}")

            asset = assets.get(image)
            if not isinstance(asset, dict):
                raise ValueError("deployed provenance entry missing")
            if asset.get("origin_url") != expected_origin:
                raise ValueError(
                    f"origin mismatch expected={expected_origin!r} got={asset.get('origin_url')!r}"
                )
            if asset.get("provenance_status") not in {None, "VERIFIED"}:
                raise ValueError(f"unexpected provenance status={asset.get('provenance_status')!r}")

            if image not in checked_files:
                image_bytes, image_type = _get(
                    f"{SITE}/media/{quote(image, safe='')}?media_readback={nonce}",
                    "image/*,*/*;q=0.1",
                )
                if not image_type.startswith("image/") and not _looks_like_image(image_bytes):
                    raise ValueError(f"local media is not an image content-type={image_type or 'missing'}")
                if not _looks_like_image(image_bytes):
                    raise ValueError("local media has unsupported image signature")
                checked_files.add(image)
        except Exception as exc:
            failures.append({"story_id": story_id, "image": image, "error": f"{type(exc).__name__}: {exc}"})

    if failures:
        raise SystemExit("LIVE MEDIA READBACK FAIL: " + json.dumps(failures, ensure_ascii=False))
    print(
        f"LIVE MEDIA READBACK PASS: stories={len(expected)} unique_media={len(checked_files)} "
        f"provenance_assets={len(assets)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
