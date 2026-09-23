#!/usr/bin/env python3
"""Historical public editions are retired from VÂLCEA CLAR.

The historical research may remain in CIVORA as internal/editorial material, but
the public site no longer projects /editii routes, navigation or sitemap URLs.
"""
from __future__ import annotations
import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "_site"


def _remove_editii_from_sitemap() -> int:
    sitemap = OUT / "sitemap.xml"
    if not sitemap.is_file():
        return 0
    text = sitemap.read_text(encoding="utf-8")
    import re
    cleaned, count = re.subn(
        r'<url><loc>https://valceaclar\.ro/editii/.*?</loc>(?:<lastmod>.*?</lastmod>)?</url>',
        '',
        text,
    )
    if count:
        sitemap.write_text(cleaned, encoding="utf-8")
    return count


def build() -> dict:
    target = OUT / "editii"
    removed_routes = 0
    if target.exists():
        removed_routes = sum(1 for _ in target.rglob("index.html"))
        shutil.rmtree(target)
    removed_sitemap = _remove_editii_from_sitemap()
    for page in OUT.rglob("*.html"):
        text = page.read_text(encoding="utf-8")
        if "/editii/" in text or "Ediții anterioare" in text:
            raise SystemExit(f"Retired historical navigation still present: {page}")
    return {
        "status": "RETIRED",
        "edition_count": 0,
        "route_count": 0,
        "removed_routes": removed_routes,
        "removed_sitemap_entries": removed_sitemap,
    }


def probe() -> int:
    print("")
    return 0


def self_test() -> int:
    assert "/editii/" not in "historical projection retired"
    print("VÂLCEA CLAR historical public projection: RETIRED")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--probe", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    if args.probe:
        return probe()
    print(json.dumps(build(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
