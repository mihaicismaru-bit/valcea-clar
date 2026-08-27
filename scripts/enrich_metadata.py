#!/usr/bin/env python3
"""Enrich the generated static site with deterministic discovery/social metadata."""
from __future__ import annotations

import html
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "_site"
CONTENT = ROOT / "content"
SITE = "https://valceaclar.ro"
PREVIEW = os.getenv("VALCEA_CLAR_PREVIEW", "") == "1"
START = "<!-- VC_METADATA_START -->"
END = "<!-- VC_METADATA_END -->"


def esc(value: str) -> str:
    return html.escape(str(value), quote=True)


def load_articles() -> dict[str, dict]:
    doc = json.loads((CONTENT / "articles.json").read_text(encoding="utf-8"))
    return {str(row["id"]): row for row in doc.get("articles", []) if row.get("id")}


def canonical_from(text: str) -> str:
    match = re.search(r'<link rel="canonical" href="([^"]+)"', text)
    if not match:
        raise SystemExit("Metadata enrichment refused: canonical link missing")
    return html.unescape(match.group(1))


def strip_existing(text: str) -> str:
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END) + r"\n?", re.S)
    return pattern.sub("", text)


def meta_tag(prop: str, value: str, *, name: bool = False) -> str:
    attr = "name" if name else "property"
    return f'<meta {attr}="{esc(prop)}" content="{esc(value)}">'


def json_ld(payload: dict) -> str:
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f'<script type="application/ld+json">{raw}</script>'


def common_block(title: str, description: str, canonical: str, image_url: str | None = None) -> list[str]:
    lines = [START]
    if not PREVIEW:
        lines.append(meta_tag("robots", "max-image-preview:large", name=True))
    lines.extend(
        [
            meta_tag("twitter:card", "summary_large_image" if image_url else "summary", name=True),
            meta_tag("twitter:title", title, name=True),
            meta_tag("twitter:description", description, name=True),
        ]
    )
    if image_url:
        lines.extend(
            [
                meta_tag("og:image", image_url),
                meta_tag("twitter:image", image_url, name=True),
            ]
        )
    lines.append(END)
    return lines


def enrich_home(path: Path, text: str) -> None:
    title = "VÂLCEA CLAR — Știri din Vâlcea"
    desc = "Știri locale verificate din Vâlcea. Fapte, documente și context, publicate continuu."
    canonical = canonical_from(text)
    lines = common_block(title, desc, canonical)
    lines.insert(-1, json_ld({
        "@context": "https://schema.org",
        "@type": "NewsMediaOrganization",
        "name": "VÂLCEA CLAR",
        "url": SITE + "/",
        "email": "redactie@valceaclar.ro"
    }))
    lines.insert(-1, json_ld({
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": "VÂLCEA CLAR",
        "url": SITE + "/",
        "inLanguage": "ro-RO"
    }))
    text = strip_existing(text).replace("</head>", "\n" + "\n".join(lines) + "\n</head>", 1)
    path.write_text(text, encoding="utf-8")


def enrich_article(path: Path, article: dict) -> None:
    text = strip_existing(path.read_text(encoding="utf-8"))
    canonical = canonical_from(text)
    title = str(article.get("headline") or "VÂLCEA CLAR")
    desc = str(article.get("dek") or "Știri locale verificate din Vâlcea.")
    published = str(article.get("published") or "")
    image_name = article.get("image")
    image_url = f"{SITE}/media/{image_name}" if image_name else None
    lines = common_block(title, desc, canonical, image_url)
    lines.insert(1, meta_tag("og:type", "article"))
    if published:
        lines.insert(2, meta_tag("article:published_time", published))
    schema = {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": title,
        "description": desc,
        "datePublished": published,
        "dateModified": published,
        "inLanguage": "ro-RO",
        "mainEntityOfPage": {"@type": "WebPage", "@id": canonical},
        "author": {"@type": "Organization", "name": "Redacția VÂLCEA CLAR", "url": SITE + "/despre/"},
        "publisher": {"@type": "NewsMediaOrganization", "name": "VÂLCEA CLAR", "url": SITE + "/"},
    }
    if image_url:
        schema["image"] = [image_url]
    lines.insert(-1, json_ld(schema))
    text = text.replace("</head>", "\n" + "\n".join(lines) + "\n</head>", 1)
    path.write_text(text, encoding="utf-8")


def main() -> int:
    if not OUT.is_dir():
        raise SystemExit("Metadata enrichment refused: _site is missing; run build.py first")
    articles = load_articles()
    home = OUT / "index.html"
    enrich_home(home, home.read_text(encoding="utf-8"))
    enriched = 0
    for story_id, article in articles.items():
        page = OUT / "stiri" / story_id / "index.html"
        if not page.is_file():
            raise SystemExit(f"Metadata enrichment refused: missing story route {story_id}")
        enrich_article(page, article)
        enriched += 1
    print(f"METADATA PASS: homepage + {enriched} NewsArticle pages enriched; preview={PREVIEW}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
