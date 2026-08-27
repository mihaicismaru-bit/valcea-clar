#!/usr/bin/env python3
"""Project validated CIVORA historical editions into the public static site.

Editorial authority remains in mihaicismaru-bit/civora. This script only renders
historical reconstructions that CIVORA has explicitly released for public
projection and that pass the anti-hindsight disclosure contract.
"""
from __future__ import annotations

import argparse
import html
import json
import os
from datetime import date, timedelta
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "_site"
BASE = os.getenv("VALCEA_CLAR_BASE_PATH", "").rstrip("/")
PREVIEW = os.getenv("VALCEA_CLAR_PREVIEW", "") == "1"
SITE = "https://valceaclar.ro"
RAW = "https://raw.githubusercontent.com/mihaicismaru-bit/civora/main/valcea-clar/history"
MANIFEST_URL = RAW + "/backfills/2020.json"
DISCLOSURE = "EDIȚIE ISTORICĂ RECONSTRUITĂ"
PUBLISH_INTENT = "publish_historical"
MONTHS = [
    "ianuarie", "februarie", "martie", "aprilie", "mai", "iunie",
    "iulie", "august", "septembrie", "octombrie", "noiembrie", "decembrie",
]


def h(value) -> str:
    return html.escape(str(value), quote=True)


def u(path: str) -> str:
    path = "/" + str(path).lstrip("/")
    return (BASE + path) if BASE else path


def route_url(path: str) -> str:
    path = "/" + str(path).lstrip("/")
    if not path.endswith("/"):
        path += "/"
    return SITE + path


def day_route(value: str) -> str:
    d = date.fromisoformat(value)
    return f"/editii/{d.year:04d}/{d.month:02d}/{d.day:02d}/"


def article_route(edition_date: str, article_id: str) -> str:
    return day_route(edition_date) + str(article_id).strip("/") + "/"


def _request_json(url: str, *, allow_missing: bool = False):
    request = Request(
        url,
        headers={
            "User-Agent": "valcea-clar-history-projection/1.0",
            "Accept": "application/json",
            "Cache-Control": "no-cache",
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if allow_missing and exc.code == 404:
            return None
        raise


def _manifest():
    doc = _request_json(MANIFEST_URL, allow_missing=True)
    if not doc:
        return None
    if doc.get("contract_id") != "valcea-clar-historical-backfill-v1":
        raise SystemExit("Historical projection refused: manifest contract mismatch")
    if doc.get("edition_kind") != "historical_reconstruction":
        raise SystemExit("Historical projection refused: manifest edition kind mismatch")
    return doc


def _validate_edition(doc: dict) -> dict:
    edition_date = str(doc.get("edition_date") or "")
    date.fromisoformat(edition_date)
    if doc.get("edition_kind") != "historical_reconstruction":
        raise ValueError("historical edition kind mismatch")
    if doc.get("reader_label") != DISCLOSURE:
        raise ValueError("historical disclosure label missing")
    if doc.get("publication_claim") != "reconstructed_not_originally_published":
        raise ValueError("historical publication claim mismatch")
    if doc.get("publication_intent") != PUBLISH_INTENT:
        raise ValueError("historical publication intent is not public")
    validation = doc.get("validation") or {}
    for gate in ("anti_hindsight_gate", "source_date_gate", "factual_trace_gate"):
        if validation.get(gate) != "PASS":
            raise ValueError(f"historical validation gate failed: {gate}")
    if int(validation.get("future_information_leakage") or 0) != 0:
        raise ValueError("historical edition contains future-information leakage")
    items = doc.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("historical edition has no articles")
    for item in items:
        if not isinstance(item, dict) or not item.get("id") or not item.get("headline"):
            raise ValueError("historical article missing id/headline")
        if not [p for p in item.get("paragraphs") or [] if str(p).strip()]:
            raise ValueError(f"historical article {item.get('id')} has no body")
        sources = [s for s in item.get("sources") or [] if isinstance(s, dict) and s.get("url")]
        if not sources:
            raise ValueError(f"historical article {item.get('id')} has no source")
    return doc


def _public_editions() -> list[dict]:
    manifest = _manifest()
    if not manifest:
        return []
    if manifest.get("public_renderer_gate") != "PASS":
        return []
    if int(manifest.get("published_count") or 0) <= 0:
        return []
    start = date.fromisoformat(str(manifest["start_date"]))
    completed = date.fromisoformat(str(manifest.get("completed_through") or manifest["start_date"]))
    if completed < start:
        return []

    out = []
    current = start
    while current <= completed:
        stamp = current.isoformat()
        url = RAW + f"/editions/{stamp}.json"
        doc = _request_json(url)
        try:
            out.append(_validate_edition(doc))
        except ValueError as exc:
            raise SystemExit(f"Historical projection refused for {stamp}: {exc}") from exc
        current += timedelta(days=1)

    expected = int(manifest.get("published_count") or 0)
    if len(out) != expected:
        raise SystemExit(
            f"Historical projection refused: manifest published_count={expected} but rendered={len(out)}"
        )
    return out


def _nav() -> str:
    return (
        '<nav class="nav" aria-label="Navigație principală">'
        f'<a href="{u("/")}">Acasă</a>'
        f'<a href="{u("/stiri/")}">Ultimele</a>'
        f'<a href="{u("/editii/")}">Ediții anterioare</a>'
        f'<a href="{u("/despre/")}">Despre</a>'
        '</nav>'
    )


def _shell(title: str, body: str, desc: str, canonical_path: str, body_class: str = "") -> str:
    robots = '<meta name="robots" content="noindex,nofollow">' if PREVIEW else ""
    canonical = route_url(canonical_path)
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
<meta property="og:title" content="{h(title)}">
<meta property="og:description" content="{h(desc)}">
<meta property="og:url" content="{h(canonical)}">
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
  {_nav()}
</header>
<main id="main">{body}</main>
<footer>
  <strong>VÂLCEA CLAR</strong> · redactie@valceaclar.ro
  <div class="footer-links"><a href="{u('/despre/')}">Despre</a> · <a href="{u('/termeni/')}">Termeni</a> · <a href="{u('/confidentialitate/')}">Confidențialitate</a></div>
</footer>
</body>
</html>'''


def _disclosure(edition_date: str | None = None) -> str:
    suffix = f" pentru {h(edition_date)}" if edition_date else ""
    return (
        '<div class="status" role="note" style="margin:20px 0;border:2px solid currentColor">'
        f'<div><b>{DISCLOSURE}</b>{suffix}</div>'
        '<div>Această pagină a fost reconstruită ulterior din surse contemporane. '
        'Nu reprezintă o ediție publicată de VÂLCEA CLAR la data indicată și nu folosește informații devenite publice după cutoff-ul acelei zile.</div>'
        '</div>'
    )


def _date_label(value: str) -> str:
    d = date.fromisoformat(value)
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def _write_route(path: str, text: str) -> None:
    target = OUT / path.strip("/")
    target.mkdir(parents=True, exist_ok=True)
    (target / "index.html").write_text(text, encoding="utf-8")


def _patch_existing_navigation() -> None:
    target = f'<a href="{u("/despre/")}">Despre</a>'
    addition = f'<a href="{u("/editii/")}">Ediții anterioare</a>' + target
    for page in OUT.rglob("*.html"):
        text = page.read_text(encoding="utf-8")
        if "Ediții anterioare</a>" in text or target not in text:
            continue
        page.write_text(text.replace(target, addition), encoding="utf-8")


def _source_list(item: dict) -> str:
    return "".join(
        f'<li><a href="{h(source["url"])}" rel="nofollow noopener">{h(source.get("name") or "Sursă")}</a>'
        + (f' <span class="meta">· {h(source.get("published_date"))}</span>' if source.get("published_date") else "")
        + '</li>'
        for source in item.get("sources") or []
        if isinstance(source, dict) and source.get("url")
    )


def _render_index(editions: list[dict]) -> str:
    by_year: dict[int, list[dict]] = {}
    for edition in editions:
        d = date.fromisoformat(edition["edition_date"])
        by_year.setdefault(d.year, []).append(edition)
    sections = []
    for year in sorted(by_year, reverse=True):
        count = len(by_year[year])
        sections.append(
            '<section class="section">'
            f'<div class="section-head"><h2>{year}</h2><a href="{u(f"/editii/{year}/")}">Deschide anul →</a></div>'
            f'<p>{count} ediții istorice reconstruite publicate până acum.</p>'
            '</section>'
        )
    body = (
        '<div class="page-head"><div class="eyebrow">Arhivă documentară</div>'
        '<h1 class="page-title">Ediții anterioare</h1>'
        '<p class="page-dek">Reconstrucții cronologice ale agendei locale, realizate cu cutoff temporal strict și surse verificabile.</p></div>'
        + _disclosure()
        + ''.join(sections)
    )
    return _shell(
        "Ediții anterioare — VÂLCEA CLAR",
        body,
        "Arhiva edițiilor istorice reconstruite VÂLCEA CLAR.",
        "/editii/",
    )


def _render_year(year: int, editions: list[dict]) -> str:
    month_map: dict[int, list[dict]] = {}
    for edition in editions:
        d = date.fromisoformat(edition["edition_date"])
        if d.year == year:
            month_map.setdefault(d.month, []).append(edition)
    rows = []
    for month in sorted(month_map):
        rows.append(
            '<article class="list-row"><div>'
            f'<div class="kicker">{h(MONTHS[month - 1].upper())}</div>'
            f'<h2><a href="{u(f"/editii/{year}/{month:02d}/")}">{h(MONTHS[month - 1].title())} {year}</a></h2>'
            f'<p>{len(month_map[month])} ediții reconstruite.</p></div></article>'
        )
    body = (
        f'<div class="page-head"><div class="eyebrow">Arhivă · {year}</div><h1 class="page-title">Edițiile din {year}</h1></div>'
        + _disclosure()
        + '<div class="list">' + ''.join(rows) + '</div>'
    )
    return _shell(f"Ediții {year} — VÂLCEA CLAR", body, f"Ediții istorice reconstruite din {year}.", f"/editii/{year}/")


def _render_month(year: int, month: int, editions: list[dict]) -> str:
    month_editions = [
        e for e in editions
        if (lambda d: d.year == year and d.month == month)(date.fromisoformat(e["edition_date"]))
    ]
    rows = []
    for edition in sorted(month_editions, key=lambda e: e["edition_date"]):
        rows.append(
            '<article class="list-row"><div>'
            f'<div class="kicker">{DISCLOSURE}</div>'
            f'<h2><a href="{u(day_route(edition["edition_date"]))}">{h(_date_label(edition["edition_date"]))}</a></h2>'
            f'<p>{len(edition.get("items") or [])} articole reconstruite · cutoff {h(edition.get("cutoff_local"))}</p>'
            '</div></article>'
        )
    body = (
        f'<div class="page-head"><div class="eyebrow">Arhivă · {year}</div>'
        f'<h1 class="page-title">{h(MONTHS[month - 1].title())} {year}</h1></div>'
        + _disclosure()
        + '<div class="list">' + ''.join(rows) + '</div>'
    )
    return _shell(
        f"{MONTHS[month - 1].title()} {year} — VÂLCEA CLAR",
        body,
        f"Ediții istorice reconstruite pentru {MONTHS[month - 1]} {year}.",
        f"/editii/{year}/{month:02d}/",
    )


def _render_day(edition: dict) -> str:
    cards = []
    for item in sorted(edition.get("items") or [], key=lambda x: int(x.get("priority") or 0), reverse=True):
        cards.append(
            '<article class="list-row"><div>'
            f'<div class="kicker">{h(item.get("section") or "ȘTIRI")}</div>'
            f'<h2><a href="{u(article_route(edition["edition_date"], item["id"]))}">{h(item["headline"])}</a></h2>'
            f'<p>{h(item.get("dek") or "")}</p>'
            f'<p><a class="more-link" href="{u(article_route(edition["edition_date"], item["id"]))}">Citește articolul reconstruit →</a></p>'
            '</div></article>'
        )
    body = (
        f'<div class="page-head"><div class="eyebrow">Arhivă · {_date_label(edition["edition_date"])}</div>'
        f'<h1 class="page-title">VÂLCEA CLAR — {_date_label(edition["edition_date"])}</h1>'
        f'<p class="page-dek">Cutoff editorial: {h(edition.get("cutoff_local"))}. {len(edition.get("items") or [])} articole validate.</p></div>'
        + _disclosure(edition["edition_date"])
        + '<div class="list">' + ''.join(cards) + '</div>'
    )
    return _shell(
        f"VÂLCEA CLAR — {_date_label(edition['edition_date'])} — reconstrucție istorică",
        body,
        f"Ediție istorică reconstruită pentru {_date_label(edition['edition_date'])}.",
        day_route(edition["edition_date"]),
    )


def _render_article(edition: dict, item: dict) -> str:
    paragraphs = ''.join(f'<p>{h(p)}</p>' for p in item.get("paragraphs") or [])
    sources = _source_list(item)
    body = (
        '<article class="article">'
        f'<a class="back top-back" href="{u(day_route(edition["edition_date"]))}">← Ediția din {_date_label(edition["edition_date"])}</a>'
        + _disclosure(edition["edition_date"])
        + f'<div class="kicker">{h(item.get("section") or "ȘTIRI")}</div>'
        + f'<h1>{h(item["headline"])}</h1>'
        + f'<p class="dek">{h(item.get("dek") or "")}</p>'
        + f'<div class="story-meta"><span>Reconstrucție editorială VÂLCEA CLAR</span><span>Cutoff {h(edition.get("cutoff_local"))}</span></div>'
        + f'<div class="article-body">{paragraphs}</div>'
        + f'<section class="sources"><h2>Surse și documente</h2><p>Sursele de mai jos susțin exclusiv informația disponibilă până la cutoff-ul ediției.</p><ul>{sources}</ul></section>'
        + f'<a class="back" href="{u(day_route(edition["edition_date"]))}">← Înapoi la ediție</a>'
        + '</article>'
    )
    return _shell(
        f"{item['headline']} — VÂLCEA CLAR",
        body,
        str(item.get("dek") or ""),
        article_route(edition["edition_date"], item["id"]),
        "article-page",
    )


def _append_sitemap(routes: list[str]) -> None:
    sitemap = OUT / "sitemap.xml"
    text = sitemap.read_text(encoding="utf-8")
    if "</urlset>" not in text:
        raise SystemExit("Historical projection refused: malformed sitemap")
    additions = []
    for route in routes:
        loc = SITE + route
        if f"<loc>{loc}</loc>" not in text:
            additions.append(f"<url><loc>{loc}</loc></url>")
    if additions:
        sitemap.write_text(text.replace("</urlset>", ''.join(additions) + "</urlset>"), encoding="utf-8")


def build() -> dict:
    editions = _public_editions()
    if not editions:
        return {"status": "INACTIVE", "edition_count": 0, "route_count": 0}
    if not (OUT / "index.html").is_file() or not (OUT / "sitemap.xml").is_file():
        raise SystemExit("Historical projection requires the base site to be built first")

    _patch_existing_navigation()
    routes = ["/editii/"]
    _write_route("editii", _render_index(editions))

    years = sorted({date.fromisoformat(e["edition_date"]).year for e in editions})
    for year in years:
        route = f"/editii/{year}/"
        routes.append(route)
        _write_route(f"editii/{year}", _render_year(year, editions))
        months = sorted({
            date.fromisoformat(e["edition_date"]).month
            for e in editions
            if date.fromisoformat(e["edition_date"]).year == year
        })
        for month in months:
            route = f"/editii/{year}/{month:02d}/"
            routes.append(route)
            _write_route(f"editii/{year}/{month:02d}", _render_month(year, month, editions))

    for edition in editions:
        route = day_route(edition["edition_date"])
        routes.append(route)
        _write_route(route, _render_day(edition))
        for item in edition.get("items") or []:
            item_route = article_route(edition["edition_date"], item["id"])
            routes.append(item_route)
            _write_route(item_route, _render_article(edition, item))

    _append_sitemap(routes)
    for route in routes:
        page = OUT / route.strip("/") / "index.html"
        if not page.is_file():
            raise SystemExit(f"Historical route missing after render: {route}")
        text = page.read_text(encoding="utf-8")
        if DISCLOSURE not in text:
            raise SystemExit(f"Historical disclosure missing: {route}")
    return {"status": "PASS", "edition_count": len(editions), "route_count": len(routes), "latest": editions[-1]["edition_date"]}


def probe() -> int:
    manifest = _manifest()
    if not manifest or manifest.get("public_renderer_gate") != "PASS" or int(manifest.get("published_count") or 0) <= 0:
        print("")
        return 0
    print(day_route(str(manifest.get("completed_through"))))
    return 0


def self_test() -> int:
    fixture = {
        "edition_date": "2020-01-01",
        "edition_kind": "historical_reconstruction",
        "reader_label": DISCLOSURE,
        "publication_intent": PUBLISH_INTENT,
        "publication_claim": "reconstructed_not_originally_published",
        "validation": {
            "anti_hindsight_gate": "PASS",
            "source_date_gate": "PASS",
            "factual_trace_gate": "PASS",
            "future_information_leakage": 0,
        },
        "items": [{
            "id": "fixture-story",
            "headline": "Material istoric verificat",
            "dek": "Context verificat.",
            "paragraphs": ["Text verificat."],
            "sources": [{"name": "Sursă", "url": "https://example.invalid/source", "published_date": "2020-01-01"}],
        }],
    }
    assert _validate_edition(fixture) is fixture
    assert day_route("2020-01-01") == "/editii/2020/01/01/"
    assert article_route("2020-01-01", "fixture-story") == "/editii/2020/01/01/fixture-story/"
    assert DISCLOSURE in _render_day(fixture)
    broken = json.loads(json.dumps(fixture))
    broken["validation"]["future_information_leakage"] = 1
    try:
        _validate_edition(broken)
    except ValueError:
        pass
    else:
        raise AssertionError("future-information leakage must fail closed")
    print("VÂLCEA CLAR historical projection self-test: PASS")
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
