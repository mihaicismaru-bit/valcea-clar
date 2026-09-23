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
    image_name = str(article.get("image") or "").strip()
    image_exists = bool(image_name and (OUT / "media" / image_name).is_file())
    image_url = f"{SITE}/media/{image_name}" if image_exists else None
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


def ensure_clarificam_route() -> None:
    """Keep the canonical CLARIFICĂM product discoverable even between stories.

    Product navigation is an editorial taxonomy, not a reflection of whether a
    particular run happens to contain an explainer. An empty product page is
    preferable to silently deleting a canonical route or inventing filler.
    """
    target = OUT / "clarificam" / "index.html"
    if not target.is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            '''<!doctype html>
<html lang="ro"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#f5f2ec"><title>CLARIFICĂM — VÂLCEA CLAR</title>
<meta name="description" content="Explicații VÂLCEA CLAR despre mecanisme, cifre și documente locale.">
<link rel="canonical" href="https://valceaclar.ro/clarificam/"><meta property="og:site_name" content="VÂLCEA CLAR">
<meta property="og:title" content="CLARIFICĂM — VÂLCEA CLAR"><meta property="og:description" content="Explicații VÂLCEA CLAR despre mecanisme, cifre și documente locale.">
<meta property="og:url" content="https://valceaclar.ro/clarificam/"><link rel="stylesheet" href="/assets/site.css"></head>
<body class="theme-editorial-2026"><a class="skip" href="#main">Sari la conținut</a><header class="site-header"><div class="mast"><div class="mast-meta">Vâlcea · publicație locală</div><a class="brand" href="/">VÂLCEA CLAR</a><div class="tag">Ce se întâmplă. Ce știm. Ce contează.</div></div><nav class="nav nav-primary" aria-label="Navigație principală"><a href="/">Acasă</a><a href="/stiri/">Ultimele</a><a href="/valcea-azi/">VÂLCEA AZI</a><a href="/pe-scurt/">PE SCURT</a><a href="/clarificam/">CLARIFICĂM</a><a href="/dosar/">DOSAR</a><a class="nav-event-link" href="/unde-iesim/">UNDE IEȘIM</a><a href="/despre/">Despre</a></nav></header>
<main id="main"><section class="section"><div class="kicker">FORMAT EDITORIAL</div><h1 class="index-title">CLARIFICĂM</h1><p class="index-dek">Explicăm mecanismul real din spatele unei informații locale: ce știm, ce nu știm, ce înseamnă cifrele și ce urmează.</p><div class="empty-state"><strong>Nu există momentan un material CLARIFICĂM în fluxul public curent.</strong><p>Pagina rămâne indexabilă ca parte a structurii editoriale; nu publicăm un text slab doar pentru a umple categoria.</p></div></section></main>
<footer><strong>VÂLCEA CLAR</strong> · redactie@valceaclar.ro<div class="footer-links"><a href="/despre/">Despre</a> · <a href="/termeni/">Termeni</a> · <a href="/confidentialitate/">Confidențialitate</a></div></footer></body></html>''',
            encoding="utf-8",
        )

    # Keep the canonical product visible in the primary navigation on every
    # generated page without disturbing article or Local Life content.
    pattern = re.compile(r'(<a href="[^"]*/pe-scurt/">PE SCURT</a>)(?!<a href="[^"]*/clarificam/">)')
    for page in OUT.rglob("*.html"):
        text = page.read_text(encoding="utf-8")
        if 'href="/clarificam/"' not in text and '/pe-scurt/' in text:
            text = pattern.sub(r'\1<a href="/clarificam/">CLARIFICĂM</a>', text, count=1)
            page.write_text(text, encoding="utf-8")

    sitemap = OUT / "sitemap.xml"
    if sitemap.is_file():
        text = sitemap.read_text(encoding="utf-8")
        loc = SITE + "/clarificam/"
        if f"<loc>{loc}</loc>" not in text:
            text = text.replace("</urlset>", f"<url><loc>{loc}</loc></url></urlset>", 1)
            sitemap.write_text(text, encoding="utf-8")


def main() -> int:
    if not OUT.is_dir():
        raise SystemExit("Metadata enrichment refused: _site is missing; run build.py first")
    articles = load_articles()
    home = OUT / "index.html"
    enrich_home(home, home.read_text(encoding="utf-8"))
    enriched = 0
    image_enriched = 0
    for story_id, article in articles.items():
        page = OUT / "stiri" / story_id / "index.html"
        if not page.is_file():
            raise SystemExit(f"Metadata enrichment refused: missing story route {story_id}")
        if article.get("image") and (OUT / "media" / str(article["image"])).is_file():
            image_enriched += 1
        enrich_article(page, article)
        enriched += 1
    ensure_clarificam_route()
    print(
        f"METADATA PASS: homepage + {enriched} NewsArticle pages enriched; "
        f"image_pages={image_enriched}; preview={PREVIEW}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
