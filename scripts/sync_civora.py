#!/usr/bin/env python3
"""Synchronize the public VÂLCEA CLAR projection from the canonical CIVORA feed.

CIVORA owns editorial generation, publication eligibility and visual provenance.
This repository owns only deterministic public presentation and GitHub Pages
publication. Verified CIVORA visuals are projected as build-time media mirrors;
the public HTML never needs to hotlink a remote image at runtime.
"""
from __future__ import annotations

import hashlib
import json
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


def _fetch_feed() -> dict:
    request = Request(
        FEED_URL,
        headers={
            "User-Agent": "valcea-clar-public-sync/1.1",
            "Accept": "application/json",
            "Cache-Control": "no-cache",
        },
    )
    with urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if payload.get("canonical_domain") != EXPECTED_DOMAIN:
        raise SystemExit("Refusing sync: CIVORA canonical_domain mismatch")
    if payload.get("publication_model") != EXPECTED_MODEL:
        raise SystemExit("Refusing sync: CIVORA publication model mismatch")
    stories = payload.get("stories")
    if not isinstance(stories, list) or not stories:
        raise SystemExit("Refusing sync: CIVORA feed has no stories")
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


def _normalize_visual(story_id: str, visual) -> dict | None:
    """Return a safe build-time mirror contract for a verified CIVORA visual."""
    if not isinstance(visual, dict):
        return None
    if str(visual.get("provenance_status") or "").upper() != "VERIFIED":
        return None
    if visual.get("synthetic") is True:
        return None

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
    }


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

    canonical_visual = _normalize_visual(story_id, story.get("visual"))
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


def main() -> int:
    feed = _fetch_feed()
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
    articles = [
        _normalize_story(story, rank, feed, old_by_id, local_media)
        for rank, story in enumerate(ordered_stories)
    ]
    ids = [row["id"] for row in articles]
    if len(ids) != len(set(ids)):
        raise SystemExit("Refusing sync: duplicate canonical story ids")

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
                "schema_version": "1.2",
                "source": FEED_URL,
                "source_generated_at": generated_at,
                "source_schema_version": feed.get("schema_version"),
                "publication_model": feed.get("publication_model"),
                "presentation_order": "freshness_first_then_source_priority",
                "story_count": len(articles),
                "verified_visual_count": verified_visual_count,
                "lead_story_id": articles[0]["id"],
                "lead_published_at": articles[0]["published"],
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
        f"CIVORA sync: PASS stories={len(articles)} visuals={verified_visual_count} "
        f"lead={articles[0]['id']} published={articles[0]['published']} "
        f"generated_at={generated_at} sha256={digest[:12]}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
