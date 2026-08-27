#!/usr/bin/env python3
"""Synchronize the public VÂLCEA CLAR projection from the canonical CIVORA feed.

CIVORA owns editorial generation and publication eligibility. This repository owns
only the deterministic public presentation and GitHub Pages deployment.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
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
EXPECTED_DOMAIN = "valceaclar.ro"
EXPECTED_MODEL = "continuous_story_first"


def _load_json(path: Path, default):
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _fetch_feed() -> dict:
    request = Request(
        FEED_URL,
        headers={
            "User-Agent": "valcea-clar-public-sync/1.0",
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

    old = old_by_id.get(story_id, {})
    image = None
    image_caption = None

    # Preserve already-curated local media for the same story. The public repo does
    # not hotlink CIVORA/remote images; media reconciliation is a separate safe path.
    old_image = old.get("image")
    if old_image in local_media:
        image = old_image
        image_caption = old.get("image_caption")

    visual = story.get("visual") or {}
    visual_filename = visual.get("filename") if isinstance(visual, dict) else None
    if visual_filename in local_media:
        image = visual_filename
        image_caption = (
            visual.get("editorial_note")
            or visual.get("alt_text")
            or visual.get("credit")
        )

    # CIVORA feed order is the canonical homepage order. The presentation builder
    # sorts by priority, so project rank into a monotonic presentation priority and
    # keep the source priority separately for audit.
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
        "image": image,
        "canonical_source": "CIVORA",
        "canonical_path": str(story.get("path") or f"/stiri/{story_id}/"),
    }
    if image_caption:
        out["image_caption"] = str(image_caption)
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

    articles = [
        _normalize_story(story, rank, feed, old_by_id, local_media)
        for rank, story in enumerate(feed["stories"])
    ]
    ids = [row["id"] for row in articles]
    if len(ids) != len(set(ids)):
        raise SystemExit("Refusing sync: duplicate canonical story ids")

    generated_at = str(feed.get("generated_at") or "")
    public_doc = {
        "updated_local": generated_at,
        "canonical_source": FEED_URL,
        "canonical_schema_version": feed.get("schema_version"),
        "articles": articles,
    }
    rendered = json.dumps(public_doc, ensure_ascii=False, indent=2) + "\n"
    digest = hashlib.sha256(rendered.encode("utf-8")).hexdigest()

    SYNC_DIR.mkdir(parents=True, exist_ok=True)
    ARTICLES_PATH.write_text(rendered, encoding="utf-8")
    STATE_PATH.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "source": FEED_URL,
                "source_generated_at": generated_at,
                "source_schema_version": feed.get("schema_version"),
                "publication_model": feed.get("publication_model"),
                "story_count": len(articles),
                "lead_story_id": articles[0]["id"],
                "articles_sha256": digest,
                "synced_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "ownership": {
                    "editorial_engine": "mihaicismaru-bit/civora",
                    "public_projection": "mihaicismaru-bit/valcea-clar",
                    "hosting": "GitHub Pages",
                },
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        f"CIVORA sync: PASS stories={len(articles)} lead={articles[0]['id']} "
        f"generated_at={generated_at} sha256={digest[:12]}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
