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

# Product URLs are durable navigation/indexing surfaces, not a reflection of
# whether the current live story set happens to contain that format. Keeping
# these routes stable prevents a sparse news cycle from breaking navigation or
# making Google see canonical product pages disappear and reappear.
DURABLE_PRODUCT_ROUTES = {
    "valcea-azi": ("VÂLCEA AZI", "Știrile curente și evoluțiile importante din județ."),
    "pe-scurt": ("PE SCURT", "Informația esențială, verificată și pusă rapid în context."),
    "clarificam": ("CLARIFICĂM", "Explicații despre mecanisme, cifre și documente, cu limitele verificării la vedere."),
    "verificat": ("VERIFICAT", "Afirmații și cifre confruntate cu sursele disponibile."),
    "ce-urmeaza": ("CE URMEAZĂ", "Termene, următorii pași și întrebările care rămân deschise."),
    "dosar": ("DOSAR", "Context extins, cronologie, documente, bani și actori relevanți."),
    "profil-oameni": ("PROFIL/OAMENI", "Profiluri locale construite din fapte și context verificat."),
    "ancheta": ("ANCHETĂ", "Investigații documentate, cu standard de probă și drept la replică."),
    "weekend-clar": ("WEEKEND CLAR", "Selecție verificată pentru timpul liber în Vâlcea."),
    "pamflet-satira": ("PAMFLET/SATIRĂ", "Satiră etichetată clar, pornind de la un nucleu factual verificat."),
}
DURABLE_NAV_ORDER = (
    ("/valcea-azi/", "VÂLCEA AZI"),
    ("/pe-scurt/", "PE SCURT"),
    ("/clarificam/", "CLARIFICĂM"),
    ("/verificat/", "VERIFICAT"),
    ("/ce-urmeaza/", "CE URMEAZĂ"),
    ("/dosar/", "DOSAR"),
    ("/profil-oameni/", "PROFIL/OAMENI"),
    ("/ancheta/", "ANCHETĂ"),
)


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


def _empty_product_page(slug: str, title: str, description: str) -> str:
    canonical = f"{SITE}/{slug}/"
    nav = ''.join(f'<a href="{esc(path)}">{esc(label)}</a>' for path, label in DURABLE_NAV_ORDER)
    return f'''<!doctype html>
<html lang="ro"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} — VÂLCEA CLAR</title><meta name="description" content="{esc(description)}">
<link rel="canonical" href="{esc(canonical)}"><link rel="stylesheet" href="/assets/site.css">
<meta name="robots" content="max-image-preview:large"></head>
<body class="theme-editorial-2026"><a class="skip" href="#main">Sari la conținut</a>
<header class="site-header"><div class="mast"><div class="mast-meta">Vâlcea · publicație locală</div><a class="brand" href="/">VÂLCEA CLAR</a><div class="tag">Ce se întâmplă. Ce știm. Ce contează.</div></div>
<nav class="nav nav-primary" aria-label="Navigație principală"><a href="/">Acasă</a><a href="/stiri/">Ultimele</a>{nav}<a class="nav-event-link" href="/unde-iesim/">UNDE IEȘIM</a><a href="/despre/">Despre</a></nav></header>
<main id="main"><div class="page-head"><div class="eyebrow">Format editorial</div><h1 class="page-title">{esc(title)}</h1><p class="page-dek">{esc(description)}</p></div>
<div class="empty-state"><strong>Niciun material activ în acest format.</strong><p>Ruta rămâne stabilă și indexabilă; publicăm aici numai când există un material care trece standardele editoriale.</p></div></main>
<footer><strong>VÂLCEA CLAR</strong> · redactie@valceaclar.ro</footer></body></html>'''


def ensure_durable_product_routes() -> int:
    """Keep product navigation/routes stable without manufacturing filler stories."""
    created = 0
    for slug, (title, description) in DURABLE_PRODUCT_ROUTES.items():
        route = OUT / slug / "index.html"
        if not route.is_file():
            route.parent.mkdir(parents=True, exist_ok=True)
            route.write_text(_empty_product_page(slug, title, description), encoding="utf-8")
            created += 1

    # Navigation must point only to real routes. Insert any missing durable
    # product link immediately before UNDE IEȘIM on every generated page.
    event_anchor = '<a class="nav-event-link" href="/unde-iesim/">UNDE IEȘIM</a>'
    durable_links = ''.join(
        f'<a href="{esc(path)}">{esc(label)}</a>'
        for path, label in DURABLE_NAV_ORDER
    )
    for page in OUT.rglob("*.html"):
        text = page.read_text(encoding="utf-8")
        if event_anchor not in text:
            continue
        # Rebuild only the product segment when any durable product is absent;
        # preserve topic navigation and the rest of the document verbatim.
        missing = [path for path, _ in DURABLE_NAV_ORDER if f'href="{path}"' not in text]
        if missing:
            existing_pattern = re.compile(
                r'(?:(?:<a href="/(?:valcea-azi|pe-scurt|clarificam|verificat|ce-urmeaza|dosar|profil-oameni|ancheta)/">.*?</a>))*'
                + re.escape(event_anchor)
            )
            replacement = durable_links + event_anchor
            new_text, count = existing_pattern.subn(replacement, text, count=1)
            if count:
                page.write_text(new_text, encoding="utf-8")

    sitemap = OUT / "sitemap.xml"
    if sitemap.is_file():
        xml = sitemap.read_text(encoding="utf-8")
        additions = []
        for slug in DURABLE_PRODUCT_ROUTES:
            loc = f"{SITE}/{slug}/"
            if f"<loc>{loc}</loc>" not in xml:
                additions.append(f"<url><loc>{loc}</loc></url>")
        if additions:
            if "</urlset>" not in xml:
                raise SystemExit("Metadata enrichment refused: malformed sitemap.xml")
            xml = xml.replace("</urlset>", "".join(additions) + "</urlset>", 1)
            sitemap.write_text(xml, encoding="utf-8")
    return created


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
    created_routes = ensure_durable_product_routes()
    print(
        f"METADATA PASS: homepage + {enriched} NewsArticle pages enriched; "
        f"image_pages={image_enriched}; durable_product_routes_created={created_routes}; preview={PREVIEW}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
