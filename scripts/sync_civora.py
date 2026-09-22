#!/usr/bin/env python3
"""Synchronize the public VÂLCEA CLAR projection from the canonical CIVORA feed.

CIVORA owns editorial generation, publication eligibility and visual provenance.
This repository owns only deterministic public presentation and GitHub Pages
publication. Verified CIVORA visuals are projected as build-time media mirrors;
the public HTML never needs to hotlink a remote image at runtime.

The public projection is durable: a story may age out of the live reader feed
without becoming retracted. Current CIVORA runtime manifest + route evidence is
therefore used to retain such already-published NewsArticle routes. Missing or
invalid durable evidence fails closed instead of silently deleting a story.
"""
from __future__ import annotations

import hashlib
import html as html_lib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content"
SYNC_DIR = ROOT / "sync"
ARTICLES_PATH = CONTENT / "articles.json"
MEDIA_PATH = CONTENT / "media.json"
STATE_PATH = SYNC_DIR / "civora_state.json"

FEED_URL = (
    "https://raw.githubusercontent.com/mihaicismaru-bit/civora/main/"
    "valcea-clar/site/runtime/live-feed.json"
)
RUNTIME_MANIFEST_URL = (
    "https://raw.githubusercontent.com/mihaicismaru-bit/civora/main/"
    "valcea-clar/site/runtime/stiri/manifest.json"
)
CIVORA_RUNTIME_RAW = (
    "https://raw.githubusercontent.com/mihaicismaru-bit/civora/main/"
    "valcea-clar/site/runtime"
)
EXPECTED_DOMAIN = "valceaclar.ro"
EXPECTED_MODEL = "continuous_story_first"
SAFE_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def _load_json(path: Path, default):
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _fresh_url(url: str) -> str:
    separator = '&' if '?' in url else '?'
    return f"{url}{separator}vc_sync={time.time_ns()}"


def _fetch_json(url: str, *, agent: str) -> dict:
    request = Request(
        _fresh_url(url),
        headers={
            "User-Agent": agent,
            "Accept": "application/json",
            "Cache-Control": "no-cache, no-store, max-age=0",
        },
    )
    with urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"Refusing sync: non-object JSON from {url}")
    return payload


def _fetch_text(url: str) -> str:
    request = Request(
        _fresh_url(url),
        headers={
            "User-Agent": "valcea-clar-public-sync/1.2",
            "Accept": "text/html,*/*;q=0.8",
            "Cache-Control": "no-cache, no-store, max-age=0",
        },
    )
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def _fetch_feed() -> dict:
    payload = _fetch_json(FEED_URL, agent="valcea-clar-public-sync/1.2")
    if payload.get("canonical_domain") != EXPECTED_DOMAIN:
        raise SystemExit("Refusing sync: CIVORA canonical_domain mismatch")
    if payload.get("publication_model") != EXPECTED_MODEL:
        raise SystemExit("Refusing sync: CIVORA publication model mismatch")
    stories = payload.get("stories")
    if not isinstance(stories, list) or not stories:
        raise SystemExit("Refusing sync: CIVORA feed has no stories")
    return payload


def _fetch_runtime_manifest() -> dict:
    payload = _fetch_json(RUNTIME_MANIFEST_URL, agent="valcea-clar-public-sync/1.2")
    if payload.get("publication_model") != EXPECTED_MODEL:
        raise SystemExit("Refusing sync: CIVORA runtime manifest model mismatch")
    stories = payload.get("stories")
    if not isinstance(stories, list) or not stories:
        raise SystemExit("Refusing sync: CIVORA runtime manifest has no stories")
    return payload


def _published_at(story: dict, feed: dict) -> str:
    return str(
        story.get("first_published_at")
        or story.get("published_at")
        or story.get("updated_at")
        or feed.get("generated_at")
        or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )


def _freshness_key(story: dict, feed: dict):
    value = _published_at(story, feed)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        timestamp = parsed.timestamp()
    except ValueError:
        timestamp = 0.0
    return (timestamp, int(story.get("priority") or 0), str(story.get("id") or ""))


def _normalize_sources(value) -> list[dict]:
    out = []
    for row in value or []:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "Sursă").strip()
        url = str(row.get("url") or "").strip()
        if not url:
            continue
        item = {"name": name, "url": url}
        tier = row.get("tier")
        if tier:
            item["tier"] = str(tier)
        out.append(item)
    return out


def _image_extension(*values: str) -> str:
    for value in values:
        if not value:
            continue
        suffix = Path(unquote(urlparse(value).path)).suffix.lower()
        if suffix in SAFE_IMAGE_EXTENSIONS:
            return ".jpg" if suffix == ".jpeg" else suffix
    return ".jpg"


def _visual_is_editorial_card(visual: dict) -> bool:
    fields = [
        visual.get("editorial_note"),
        visual.get("alt_text"),
        visual.get("credit"),
        visual.get("rights_basis"),
        visual.get("relative_url"),
        visual.get("public_url"),
        visual.get("source_url"),
        visual.get("filename"),
        visual.get("asset_type"),
        visual.get("visual_type"),
        visual.get("kind"),
    ]
    haystack = " ".join(str(value or "").lower() for value in fields)
    markers = (
        "card editorial",
        "editorial card",
        "editorial_card",
        "social card",
        "social_card",
        "original_editorial_layout",
        "/social/editorial/",
        "social/editorial",
    )
    return any(marker in haystack for marker in markers)


def _normalize_visual(story_id: str, visual) -> dict | None:
    """Return a safe build-time mirror contract for a verified CIVORA visual."""
    if not isinstance(visual, dict):
        return None
    if str(visual.get("provenance_status") or "").upper() != "VERIFIED":
        return None

    synthetic = visual.get("synthetic") is True
    depicts_real_scene = visual.get("depicts_real_scene")
    is_editorial_card = _visual_is_editorial_card(visual)
    site_eligible = not is_editorial_card
    if synthetic:
        site_eligible = site_eligible and depicts_real_scene is False

    public_url = str(visual.get("public_url") or "").strip()
    source_url = str(visual.get("source_url") or public_url).strip()
    relative_url = str(visual.get("relative_url") or "").strip()
    if not public_url or urlparse(public_url).scheme != "https":
        return None

    fetch_url = public_url
    filename = str(visual.get("filename") or "").strip()
    if relative_url.startswith("/media/"):
        fetch_url = CIVORA_RUNTIME_RAW + relative_url
        filename = Path(unquote(urlparse(relative_url).path)).name or filename
    elif (urlparse(public_url).hostname or "").lower() == "valceaclar.ro" and urlparse(public_url).path.startswith("/media/"):
        fetch_url = CIVORA_RUNTIME_RAW + urlparse(public_url).path
        filename = Path(unquote(urlparse(public_url).path)).name or filename

    if not filename or Path(filename).suffix.lower() not in SAFE_IMAGE_EXTENSIONS:
        ext = _image_extension(public_url, source_url)
        fingerprint = hashlib.sha256(public_url.encode("utf-8")).hexdigest()[:16]
        filename = f"civora-{fingerprint}{ext}"
    filename = Path(filename).name

    caption = (
        visual.get("editorial_note")
        or visual.get("alt_text")
        or visual.get("credit")
        or "Imagine verificată prin CIVORA."
    )
    return {
        "image": filename,
        "image_caption": str(caption),
        "image_origin_url": public_url,
        "image_fetch_url": fetch_url,
        "image_source_url": source_url,
        "image_credit": str(visual.get("credit") or ""),
        "image_rights_basis": str(visual.get("rights_basis") or ""),
        "image_license_url": str(visual.get("license_url") or ""),
        "image_provenance_status": "VERIFIED",
        "image_contextual_archive": bool(visual.get("contextual_archive")),
        "image_captured_at": str(visual.get("captured_at") or ""),
        "image_story_id": story_id,
        "image_site_eligible": site_eligible,
        "image_synthetic": synthetic,
        "image_depicts_real_scene": depicts_real_scene,
        "image_asset_role": "social_card" if is_editorial_card else "site_visual",
    }


def _editorial_product(story: dict) -> str:
    """Return the reader-facing product signal without stringifying metadata objects."""
    for key in ('editorial_product', 'product_type', 'product', 'format', 'story_type'):
        value = story.get(key)
        if isinstance(value, dict):
            nested = (
                value.get('reader_product')
                or value.get('product')
                or value.get('format')
                or value.get('writer_format')
            )
            if nested:
                return str(nested).strip()
            continue
        text = str(value or '').strip()
        if text:
            return text
    return ''


def _normalize_story(story: dict, rank: int, feed: dict, old_by_id: dict, local_media: set[str]) -> dict:
    story_id = str(story.get("id") or "").strip()
    headline = str(story.get("headline") or "").strip()
    if not story_id or not headline:
        raise SystemExit("Refusing sync: canonical story missing id/headline")

    paragraphs = [str(x).strip() for x in story.get("paragraphs") or [] if str(x).strip()]
    if not paragraphs:
        dek = str(story.get("dek") or "").strip()
        if dek:
            paragraphs = [dek]
    if not paragraphs:
        raise SystemExit(f"Refusing sync: canonical story {story_id} has no body")

    out = {
        "id": story_id,
        "section": str(story.get("section") or "ȘTIRI"),
        "priority": 1_000_000 - rank,
        "source_priority": int(story.get("priority") or 0),
        "canonical_rank": rank,
        "headline": headline,
        "dek": str(story.get("dek") or paragraphs[0]),
        "paragraphs": paragraphs,
        "sources": _normalize_sources(story.get("sources")),
        "published": _published_at(story, feed),
        "image": None,
        "canonical_source": "CIVORA",
        "canonical_path": str(story.get("path") or f"/stiri/{story_id}/"),
    }
    editorial_product = _editorial_product(story)
    if editorial_product:
        out["editorial_product"] = editorial_product

    canonical_visual = _normalize_visual(story_id, story.get("site_visual") or story.get("visual"))
    if canonical_visual:
        out.update(canonical_visual)
    else:
        old = old_by_id.get(story_id, {})
        old_image = old.get("image")
        if old_image in local_media:
            out["image"] = old_image
            if old.get("image_caption"):
                out["image_caption"] = str(old["image_caption"])

    return out


def _plain_text(fragment: str) -> str:
    return " ".join(
        html_lib.unescape(re.sub(r"<[^>]+>", " ", fragment)).split()
    ).strip()


def _extract_runtime_archive_story(
    manifest_story: dict,
    rank: int,
    old_by_id: dict,
    local_media: set[str],
) -> dict:
    story_id = str(manifest_story.get("id") or "").strip()
    path = str(manifest_story.get("path") or "").strip()
    canonical = str(manifest_story.get("canonical") or "").strip()
    expected_path = f"/stiri/{story_id}/"
    expected_canonical = f"https://valceaclar.ro{expected_path}"

    if (
        not story_id
        or path != expected_path
        or canonical != expected_canonical
        or manifest_story.get("public_ux_authorized") is not True
        or manifest_story.get("structured_data_type") != "NewsArticle"
    ):
        raise SystemExit(f"Refusing sync: invalid durable manifest contract for {story_id or '<missing-id>'}")

    route_url = f"{CIVORA_RUNTIME_RAW}/stiri/{story_id}/index.html"
    page = _fetch_text(route_url)
    if f'<link rel="canonical" href="{expected_canonical}">' not in page:
        raise SystemExit(f"Refusing sync: durable route canonical mismatch for {story_id}")

    scripts = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        page,
        flags=re.IGNORECASE | re.DOTALL,
    )
    news = None
    for raw in scripts:
        try:
            candidate = json.loads(html_lib.unescape(raw))
        except json.JSONDecodeError:
            continue
        if (
            isinstance(candidate, dict)
            and candidate.get("@type") == "NewsArticle"
            and candidate.get("url") == expected_canonical
        ):
            news = candidate
            break
    if not news:
        raise SystemExit(f"Refusing sync: durable route has no exact NewsArticle JSON-LD for {story_id}")

    headline = str(news.get("headline") or "").strip()
    dek = str(news.get("description") or "").strip()
    section = str(news.get("articleSection") or "ȘTIRI").strip()
    published = str(news.get("datePublished") or manifest_story.get("published_at") or "").strip()
    h1_match = re.search(r"<h1[^>]*>(.*?)</h1>", page, flags=re.IGNORECASE | re.DOTALL)
    if not headline or not h1_match or _plain_text(h1_match.group(1)) != headline:
        raise SystemExit(f"Refusing sync: durable route headline mismatch for {story_id}")

    body_match = re.search(
        r'<div[^>]+class=["\'][^"\']*\barticle-body\b[^"\']*["\'][^>]*>(.*?)</div>',
        page,
        flags=re.IGNORECASE | re.DOTALL,
    )
    paragraphs = []
    if body_match:
        paragraphs = [
            _plain_text(fragment)
            for fragment in re.findall(r"<p[^>]*>(.*?)</p>", body_match.group(1), flags=re.IGNORECASE | re.DOTALL)
        ]
        paragraphs = [value for value in paragraphs if value]
    if not paragraphs:
        raise SystemExit(f"Refusing sync: durable route has no article body for {story_id}")

    sources_match = re.search(
        r'<section[^>]+class=["\'][^"\']*(?:article-sources|sources)\b[^"\']*["\'][^>]*>(.*?)</section>',
        page,
        flags=re.IGNORECASE | re.DOTALL,
    )
    sources = []
    if sources_match:
        for href, label in re.findall(
            r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
            sources_match.group(1),
            flags=re.IGNORECASE | re.DOTALL,
        ):
            href = html_lib.unescape(href).strip()
            parsed = urlparse(href)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                continue
            sources.append({"name": _plain_text(label) or "Sursă", "url": href})
    if not sources:
        raise SystemExit(f"Refusing sync: durable route has no external sources for {story_id}")

    old = old_by_id.get(story_id, {})
    out = {
        "id": story_id,
        "section": section,
        "priority": 1_000_000 - rank,
        "source_priority": int(old.get("source_priority") or 0),
        "canonical_rank": rank,
        "headline": headline,
        "dek": dek or paragraphs[0],
        "paragraphs": paragraphs,
        "sources": sources,
        "published": published,
        "image": None,
        "canonical_source": "CIVORA",
        "canonical_path": expected_path,
        "archive_only": True,
    }
    old_image = old.get("image")
    if old_image in local_media:
        out["image"] = old_image
        if old.get("image_caption"):
            out["image_caption"] = str(old["image_caption"])
    return out


def main() -> int:
    feed = _fetch_feed()
    runtime_manifest = _fetch_runtime_manifest()
    old_doc = _load_json(ARTICLES_PATH, {"articles": []})
    old_by_id = {
        str(row.get("id")): row
        for row in old_doc.get("articles", [])
        if isinstance(row, dict) and row.get("id")
    }
    media_doc = _load_json(MEDIA_PATH, [])
    local_media = {
        str(row.get("file"))
        for row in media_doc
        if isinstance(row, dict) and row.get("file")
    }

    ordered_stories = sorted(
        feed["stories"],
        key=lambda story: _freshness_key(story, feed),
        reverse=True,
    )
    current_articles = [
        _normalize_story(story, rank, feed, old_by_id, local_media)
        for rank, story in enumerate(ordered_stories)
    ]
    current_ids = [row["id"] for row in current_articles]
    if len(current_ids) != len(set(current_ids)):
        raise SystemExit("Refusing sync: duplicate canonical story ids")

    authorized_manifest = []
    seen_manifest_ids = set()
    for row in runtime_manifest.get("stories", []):
        if not isinstance(row, dict):
            continue
        story_id = str(row.get("id") or "").strip()
        if not story_id:
            raise SystemExit("Refusing sync: runtime manifest story missing id")
        if story_id in seen_manifest_ids:
            raise SystemExit(f"Refusing sync: duplicate runtime manifest story id {story_id}")
        seen_manifest_ids.add(story_id)
        if row.get("public_ux_authorized") is True and row.get("structured_data_type") == "NewsArticle":
            authorized_manifest.append(row)

    authorized_ids = {str(row["id"]) for row in authorized_manifest}
    unexpected_live = sorted(set(current_ids) - authorized_ids)
    if unexpected_live:
        raise SystemExit(
            "Refusing sync: live feed contains stories absent from authorized runtime manifest: "
            + ", ".join(unexpected_live[:10])
        )

    current_id_set = set(current_ids)
    archive_manifest = [
        row for row in authorized_manifest
        if str(row.get("id")) not in current_id_set
    ]
    archive_manifest.sort(
        key=lambda row: str(row.get("published_at") or ""),
        reverse=True,
    )
    archive_articles = [
        _extract_runtime_archive_story(
            row,
            len(current_articles) + offset,
            old_by_id,
            local_media,
        )
        for offset, row in enumerate(archive_manifest)
    ]
    articles = current_articles + archive_articles

    ids = [row["id"] for row in articles]
    if len(ids) != len(set(ids)):
        raise SystemExit("Refusing sync: duplicate projected story ids")
    if set(ids) != authorized_ids:
        missing = sorted(authorized_ids - set(ids))
        extra = sorted(set(ids) - authorized_ids)
        raise SystemExit(
            f"Refusing sync: projected story set diverges from authorized runtime manifest "
            f"missing={missing[:10]} extra={extra[:10]}"
        )

    generated_at = str(feed.get("generated_at") or "")
    public_doc = {
        "updated_local": generated_at,
        "canonical_source": FEED_URL,
        "canonical_schema_version": feed.get("schema_version"),
        "presentation_order": "freshness_first_then_source_priority",
        "articles": articles,
    }
    rendered = json.dumps(public_doc, ensure_ascii=False, indent=2) + "\n"
    digest = hashlib.sha256(rendered.encode("utf-8")).hexdigest()

    SYNC_DIR.mkdir(parents=True, exist_ok=True)
    ARTICLES_PATH.write_text(rendered, encoding="utf-8")
    verified_visual_count = sum(1 for row in articles if row.get("image_provenance_status") == "VERIFIED")
    STATE_PATH.write_text(
        json.dumps(
            {
                "schema_version": "1.3",
                "source": FEED_URL,
                "runtime_manifest_source": RUNTIME_MANIFEST_URL,
                "source_generated_at": generated_at,
                "source_schema_version": feed.get("schema_version"),
                "publication_model": feed.get("publication_model"),
                "presentation_order": "freshness_first_then_source_priority",
                "story_count": len(articles),
                "current_story_count": len(current_articles),
                "archive_story_count": len(archive_articles),
                "verified_visual_count": verified_visual_count,
                "lead_story_id": current_articles[0]["id"],
                "lead_published_at": current_articles[0]["published"],
                "articles_sha256": digest,
                "synced_at": generated_at,
                "ownership": {
                    "editorial_engine": "mihaicismaru-bit/civora",
                    "public_projection": "mihaicismaru-bit/valcea-clar",
                    "hosting": "GitHub Pages",
                    "visual_provenance": "CIVORA",
                    "visual_delivery": "build_time_local_mirror",
                },
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        f"CIVORA sync: PASS stories={len(articles)} current={len(current_articles)} "
        f"archive={len(archive_articles)} visuals={verified_visual_count} "
        f"lead={current_articles[0]['id']} published={current_articles[0]['published']} "
        f"generated_at={generated_at} sha256={digest[:12]}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
