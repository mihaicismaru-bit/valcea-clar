#!/usr/bin/env python3
"""Reconcile public projection with CIVORA story currentness and Local Life events.

The regular public sync owns article content. This second deterministic gate owns
only two projection facts that must not be inferred from compatibility ordering:
which authorized stories are current, and which structured Local Life events are
eligible for the public event inventory.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content"
SYNC = ROOT / "sync"
ARTICLES = CONTENT / "articles.json"
EVENTS = CONTENT / "events.json"
STATE = SYNC / "civora_state.json"
TZ = ZoneInfo("Europe/Bucharest")
MANIFEST_URL = "https://raw.githubusercontent.com/mihaicismaru-bit/civora/main/valcea-clar/site/runtime/stiri/manifest.json"
EVENTS_URL = "https://raw.githubusercontent.com/mihaicismaru-bit/civora/main/valcea-clar/editorial/local_life_events.json"


def fetch_json(url: str) -> dict:
    req = Request(url, headers={"User-Agent": "valcea-clar-public-reconcile/1.0", "Cache-Control": "no-cache"})
    with urlopen(req, timeout=30) as response:
        value = json.loads(response.read().decode("utf-8"))
    if not isinstance(value, dict):
        raise SystemExit(f"Refusing reconciliation: non-object JSON from {url}")
    return value


def load(path: Path, default):
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def parse_dt(value):
    text = str(value or "").strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ)
    return dt.astimezone(TZ)


def reconcile_articles(article_doc: dict, manifest: dict) -> tuple[dict, list[str], list[str]]:
    rows = [row for row in manifest.get("stories") or [] if isinstance(row, dict) and row.get("id")]
    by_id = {str(row["id"]): row for row in rows}
    current_ids = [
        str(row["id"])
        for row in rows
        if row.get("public_ux_authorized") is True
        and row.get("structured_data_type") == "NewsArticle"
        and row.get("active_now") is True
        and str(row.get("archive_status") or "active").lower() == "active"
    ]
    authorized_ids = {
        str(row["id"])
        for row in rows
        if row.get("public_ux_authorized") is True and row.get("structured_data_type") == "NewsArticle"
    }
    articles = [row for row in article_doc.get("articles") or [] if isinstance(row, dict) and row.get("id")]
    projected_ids = {str(row["id"]) for row in articles}
    if projected_ids != authorized_ids:
        raise SystemExit(
            "Refusing reconciliation: public article set differs from authorized CIVORA manifest "
            f"missing={sorted(authorized_ids-projected_ids)[:10]} extra={sorted(projected_ids-authorized_ids)[:10]}"
        )

    def published_ts(row: dict) -> float:
        dt = parse_dt(row.get("published"))
        return dt.timestamp() if dt else 0.0

    current_set = set(current_ids)
    current = sorted(
        [row for row in articles if str(row["id"]) in current_set],
        key=lambda row: (published_ts(row), int(row.get("source_priority") or 0), str(row.get("id") or "")),
        reverse=True,
    )
    archive = sorted(
        [row for row in articles if str(row["id"]) not in current_set],
        key=lambda row: (published_ts(row), int(row.get("source_priority") or 0), str(row.get("id") or "")),
        reverse=True,
    )
    for index, row in enumerate(current):
        row["archive_only"] = False
        row["active_now"] = True
        row["archive_status"] = "active"
        row["priority"] = 2_000_000 - index
    for index, row in enumerate(archive):
        row["archive_only"] = True
        row["active_now"] = False
        row["archive_status"] = str((by_id.get(str(row["id"])) or {}).get("archive_status") or "published_archive")
        row["priority"] = 1_000_000 - index

    article_doc["articles"] = current + archive
    article_doc["current_story_ids"] = [str(row["id"]) for row in current]
    article_doc["archive_story_ids"] = [str(row["id"]) for row in archive]
    article_doc["currentness_source"] = MANIFEST_URL
    return article_doc, [str(row["id"]) for row in current], [str(row["id"]) for row in archive]


def event_start_iso(row: dict) -> str:
    date = str(row.get("event_start") or "").strip()
    time = str(row.get("start_time") or "").strip()
    if not date:
        raise ValueError("event_start_missing")
    if time:
        return f"{date}T{time}:00+03:00" if len(time) == 5 else f"{date}T{time}+03:00"
    return f"{date}T00:00:00+03:00"


def public_event(raw: dict) -> dict:
    event_id = str(raw.get("event_id") or "").strip()
    fingerprint = str(raw.get("fingerprint") or "").strip()
    source_url = str(raw.get("source_url") or "").strip()
    source_tier = str(raw.get("source_tier") or "").strip()
    checked_at = str(raw.get("checked_at") or "").strip()
    if not event_id or not fingerprint or not source_url or not source_tier or not checked_at:
        raise ValueError("event_provenance_incomplete")
    status = str(raw.get("status") or "unknown").lower()
    price = raw.get("price")
    free = raw.get("free") is True
    if free:
        price_status = "free"
    elif price in (None, "", "unknown"):
        price_status = "unknown"
        price = None
    else:
        price_status = "paid"
    sources = [{"url": source_url, "tier": source_tier, "role": "canonical_event_source"}]
    out = {
        "id": event_id,
        "event_id": event_id,
        "fingerprint": fingerprint,
        "story_id": None,
        "title": str(raw.get("title") or "").strip(),
        "category": str(raw.get("category") or "Eveniment").strip().title(),
        "start": event_start_iso(raw),
        "event_start": str(raw.get("event_start") or "").strip(),
        "event_end": raw.get("event_end") or raw.get("event_start"),
        "start_time": raw.get("start_time"),
        "doors_time": raw.get("doors_time"),
        "venue": str(raw.get("venue") or "").strip(),
        "locality": str(raw.get("locality") or "").strip(),
        "price_status": price_status,
        "price": price,
        "ticket_url": raw.get("ticket_url"),
        "reservation_url": raw.get("reservation_url"),
        "organiser": raw.get("organiser"),
        "source_url": source_url,
        "source_tier": source_tier,
        "sources": sources,
        "checked_at": checked_at,
        "status": status,
        "canonical_source": "CIVORA_LOCAL_LIFE",
    }
    return out


def fresh_event(row: dict, now: datetime) -> bool:
    start = parse_dt(row.get("start"))
    checked = parse_dt(row.get("checked_at"))
    if not start or not checked:
        return False
    if start.date() < now.date() or str(row.get("status") or "").lower() == "past":
        return False
    days = (start.date() - now.date()).days
    age_hours = max(0.0, (now - checked).total_seconds() / 3600.0)
    if days <= 1 and age_hours > 12:
        return False
    if days <= 7 and age_hours > 48:
        return False
    return True


def reconcile_events(existing: dict, canonical: dict, now: datetime) -> tuple[dict, list[str]]:
    old = [row for row in existing.get("events") or [] if isinstance(row, dict) and row.get("id")]
    by_id = {str(row["id"]): row for row in old}
    imported = []
    fingerprints = {str(row.get("fingerprint")) for row in old if row.get("fingerprint")}
    for raw in canonical.get("events") or []:
        if not isinstance(raw, dict):
            continue
        try:
            row = public_event(raw)
        except ValueError:
            continue
        if not fresh_event(row, now):
            continue
        fp = str(row.get("fingerprint") or "")
        event_id = str(row["id"])
        duplicate_id = next((eid for eid, candidate in by_id.items() if str(candidate.get("fingerprint") or "") == fp and eid != event_id), None)
        if duplicate_id:
            by_id.pop(duplicate_id, None)
        by_id[event_id] = row
        fingerprints.add(fp)
        imported.append(event_id)

    rows = list(by_id.values())
    rows.sort(key=lambda row: (str(row.get("event_start") or "9999-12-31"), str(row.get("start_time") or "99:99"), str(row.get("title") or "")))
    result = dict(existing)
    result["schema_version"] = "1.2"
    result["updated_at"] = now.isoformat(timespec="seconds")
    result["events"] = rows
    result["canonical_local_life_source"] = EVENTS_URL
    result["canonical_event_ids"] = imported
    result["policy"] = {
        "canonical_events_merge_by_event_id_and_fingerprint": True,
        "freshness_fail_closed": True,
        "unknown_price_never_inferred": True,
        "provenance_required": True,
    }
    return result, imported


def apply(manifest: dict, canonical_events: dict, now: datetime) -> dict:
    articles = load(ARTICLES, {"articles": []})
    events = load(EVENTS, {"events": []})
    articles, current_ids, archive_ids = reconcile_articles(articles, manifest)
    events, imported = reconcile_events(events, canonical_events, now)
    if not current_ids:
        raise SystemExit("Refusing deployment: CIVORA has no active_now story; preserve last known good public homepage")
    ARTICLES.write_text(json.dumps(articles, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    EVENTS.write_text(json.dumps(events, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    state = load(STATE, {})
    state["current_story_count"] = len(current_ids)
    state["archive_story_count"] = len(archive_ids)
    state["lead_story_id"] = current_ids[0]
    state["currentness_source"] = MANIFEST_URL
    state["local_life_source"] = EVENTS_URL
    state["local_life_event_count"] = len(imported)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"current": current_ids, "archive_count": len(archive_ids), "events": imported}


def self_test() -> int:
    manifest = {"stories": [
        {"id": "new", "public_ux_authorized": True, "structured_data_type": "NewsArticle", "active_now": True, "archive_status": "active"},
        {"id": "old", "public_ux_authorized": True, "structured_data_type": "NewsArticle", "active_now": False, "archive_status": "published_archive"},
    ]}
    articles = {"articles": [
        {"id": "old", "published": "2026-09-22T10:00:00+03:00", "priority": 9},
        {"id": "new", "published": "2026-09-23T10:00:00+03:00", "priority": 1},
    ]}
    out, current, archive = reconcile_articles(articles, manifest)
    assert current == ["new"] and archive == ["old"]
    assert out["articles"][0]["id"] == "new" and out["articles"][1]["archive_only"] is True
    now = datetime(2026, 9, 23, 18, 0, tzinfo=TZ)
    canonical = {"events": [{
        "event_id": "dragasani", "fingerprint": "fp", "title": "O noapte furtunoasă", "event_start": "2026-09-24", "start_time": "19:00", "venue": "Casa de Cultură", "locality": "Drăgășani", "category": "teatru", "price": "80–100 lei", "source_url": "https://example.test/e", "source_tier": "T2", "checked_at": "2026-09-23T17:00:00+03:00", "status": "sold_out"
    }]}
    ev, imported = reconcile_events({"events": []}, canonical, now)
    assert imported == ["dragasani"] and ev["events"][0]["locality"] == "Drăgășani"
    stale = json.loads(json.dumps(canonical)); stale["events"][0]["checked_at"] = "2026-09-22T01:00:00+03:00"
    ev2, imported2 = reconcile_events({"events": []}, stale, now)
    assert imported2 == [] and ev2["events"] == []
    print("CIVORA public currentness/events reconciliation self-test: PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    report = apply(fetch_json(MANIFEST_URL), fetch_json(EVENTS_URL), datetime.now(TZ))
    print(json.dumps({"status": "PASS", **report}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
