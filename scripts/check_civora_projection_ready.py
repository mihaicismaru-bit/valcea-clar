#!/usr/bin/env python3
"""Fail closed while CIVORA's derived public UX/media projection is still catching up.

The canonical Live Newsroom writes the editorial feed first. A separate CIVORA
workflow then reapplies reader-facing ordering and verified media. The public
GitHub Pages repository must consume only the completed derived projection, not
the short intermediate state between those two transactions.
"""
from __future__ import annotations

import json
import os
import sys
import time
from urllib.request import Request, urlopen

BASE = (
    "https://raw.githubusercontent.com/mihaicismaru-bit/civora/main/"
    "valcea-clar/site"
)
FEED_URL = BASE + "/runtime/live-feed.json"
UX_STATE_URL = BASE + "/public_ux_state.json"
MANIFEST_URL = BASE + "/runtime/stiri/manifest.json"
DEFAULT_WAIT_SECONDS = 300.0
DEFAULT_RETRY_SECONDS = 10.0
RETRYABLE_PROJECTION_ERRORS = (
    "derived Public UX is not caught up:",
    "derived Public UX is missing canonical stories:",
    "canonical feed is between newsroom and derived-media projection:",
)


def fetch_json(url: str) -> dict:
    request = Request(
        url,
        headers={
            "User-Agent": "valcea-clar-projection-readiness/1.0",
            "Accept": "application/json",
            "Cache-Control": "no-cache",
        },
    )
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def validate(feed: dict, ux: dict, manifest: dict) -> dict:
    stories = [row for row in feed.get("stories", []) if isinstance(row, dict) and row.get("id")]
    feed_ids = {str(row["id"]) for row in stories}
    if not stories:
        raise ValueError("canonical feed has no stories")
    if feed.get("canonical_domain") != "valceaclar.ro":
        raise ValueError("canonical_domain mismatch")
    if feed.get("publication_model") != "continuous_story_first":
        raise ValueError("publication_model mismatch")

    live_count = int(ux.get("live_story_count") or 0)
    ux_ids = {str(value) for value in ux.get("story_ids", []) if value}
    if live_count != len(stories):
        raise ValueError(
            f"derived Public UX is not caught up: live_story_count={live_count} feed={len(stories)}"
        )
    missing_from_ux = sorted(feed_ids - ux_ids)
    if missing_from_ux:
        raise ValueError(
            "derived Public UX is missing canonical stories: " + ", ".join(missing_from_ux)
        )

    feed_by_id = {str(row["id"]): row for row in stories}
    expected_verified_media = set()
    for row in manifest.get("stories", []):
        if not isinstance(row, dict):
            continue
        story_id = str(row.get("id") or "")
        image = row.get("image")
        if story_id not in feed_by_id or not isinstance(image, dict):
            continue
        if (
            str(image.get("provenance_status") or "").upper() == "VERIFIED"
            and image.get("public_url")
        ):
            expected_verified_media.add(story_id)

    missing_media = []
    for story_id in sorted(expected_verified_media):
        visual = feed_by_id[story_id].get("visual")
        if not isinstance(visual, dict):
            missing_media.append(story_id)
            continue
        if (
            str(visual.get("provenance_status") or "").upper() != "VERIFIED"
            or not visual.get("public_url")
            or visual.get("synthetic") is True
        ):
            missing_media.append(story_id)
    if missing_media:
        raise ValueError(
            "canonical feed is between newsroom and derived-media projection: "
            + ", ".join(missing_media)
        )

    return {
        "status": "READY",
        "feed_generated_at": feed.get("generated_at"),
        "story_count": len(stories),
        "verified_media_count": len(expected_verified_media),
    }


def retryable_projection_error(exc: BaseException) -> bool:
    if isinstance(exc, (OSError, json.JSONDecodeError)):
        return True
    return isinstance(exc, ValueError) and str(exc).startswith(RETRYABLE_PROJECTION_ERRORS)


def self_test() -> int:
    feed = {
        "canonical_domain": "valceaclar.ro",
        "publication_model": "continuous_story_first",
        "generated_at": "2026-08-27T10:00:00Z",
        "stories": [
            {
                "id": "a",
                "visual": {
                    "provenance_status": "VERIFIED",
                    "public_url": "https://valceaclar.ro/media/a.jpg",
                    "synthetic": False,
                },
            },
            {"id": "b"},
        ],
    }
    ux = {"live_story_count": 2, "story_ids": ["a", "b", "archive"]}
    manifest = {
        "stories": [
            {
                "id": "a",
                "image": {
                    "provenance_status": "VERIFIED",
                    "public_url": "https://valceaclar.ro/media/a.jpg",
                },
            }
        ]
    }
    assert validate(feed, ux, manifest)["verified_media_count"] == 1

    bad_count = dict(ux, live_story_count=1)
    try:
        validate(feed, bad_count, manifest)
    except ValueError:
        pass
    else:
        raise AssertionError("count drift did not fail closed")

    bad_feed = json.loads(json.dumps(feed))
    bad_feed["stories"][0].pop("visual")
    try:
        validate(bad_feed, ux, manifest)
    except ValueError:
        pass
    else:
        raise AssertionError("verified-media regression did not fail closed")

    assert retryable_projection_error(
        ValueError("derived Public UX is not caught up: live_story_count=1 feed=2")
    )
    assert retryable_projection_error(OSError("temporary transport failure"))
    assert not retryable_projection_error(ValueError("canonical_domain mismatch"))

    print("CIVORA derived-projection readiness self-test: PASS")
    return 0


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()

    wait_seconds = max(
        0.0,
        float(os.environ.get("CIVORA_PROJECTION_WAIT_SECONDS", DEFAULT_WAIT_SECONDS)),
    )
    retry_seconds = max(
        1.0,
        float(os.environ.get("CIVORA_PROJECTION_RETRY_SECONDS", DEFAULT_RETRY_SECONDS)),
    )
    deadline = time.monotonic() + wait_seconds
    attempt = 0

    while True:
        attempt += 1
        try:
            result = validate(
                fetch_json(FEED_URL),
                fetch_json(UX_STATE_URL),
                fetch_json(MANIFEST_URL),
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            remaining = deadline - time.monotonic()
            if not retryable_projection_error(exc) or remaining <= 0:
                print(
                    f"CIVORA derived-projection readiness: WAIT/FAIL-CLOSED: {exc}",
                    file=sys.stderr,
                )
                return 1
            sleep_for = min(retry_seconds, remaining)
            print(
                "CIVORA derived-projection readiness: WAIT: "
                f"attempt={attempt} remaining={remaining:.0f}s error={exc}",
                file=sys.stderr,
            )
            time.sleep(sleep_for)
            continue

        print(json.dumps(result, ensure_ascii=False))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
