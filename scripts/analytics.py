#!/usr/bin/env python3
"""Privacy-safe validation and aggregation for Vâlcea Clar first-party events."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "strategy" / "analytics_contract.json"
UAT_PATH = ROOT / "strategy" / "source_coverage_matrix.json"
SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{8,80}$")
SAFE_ARTICLE_ID = re.compile(r"^[a-z0-9][a-z0-9-]{2,100}$")
SAFE_CAMPAIGN = re.compile(r"^[A-Za-z0-9_-]{1,80}$")


class EventError(ValueError):
    """An event failed the analytics contract."""


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_contract() -> dict[str, Any]:
    return load_json(CONTRACT_PATH)


def load_uats() -> set[str]:
    matrix = load_json(UAT_PATH)
    return {item["name"] for item in matrix["uats"]}


def parse_time(value: Any) -> datetime:
    if not isinstance(value, str):
        raise EventError("invalid_occurred_at")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EventError("invalid_occurred_at") from exc
    if parsed.tzinfo is None:
        raise EventError("occurred_at_requires_timezone")
    return parsed


def validate_event(raw: Any, contract: dict[str, Any], uats: set[str]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise EventError("event_not_object")
    forbidden = set(contract["privacy"]["forbidden_fields"])
    present_forbidden = forbidden.intersection(raw)
    if present_forbidden:
        raise EventError("forbidden_field")
    unknown = set(raw).difference(contract["allowed_dimensions"])
    if unknown:
        raise EventError("unknown_field")

    event_name = raw.get("event")
    event_contract = contract["events"].get(event_name)
    if event_contract is None:
        raise EventError("unknown_event")
    missing = [field for field in event_contract["required"] if raw.get(field) in (None, "")]
    if missing:
        raise EventError("missing_required_field")

    if not SAFE_ID.fullmatch(str(raw.get("event_id", ""))):
        raise EventError("invalid_event_id")
    if not SAFE_ID.fullmatch(str(raw.get("session_id", ""))):
        raise EventError("invalid_session_id")
    visitor_id = raw.get("visitor_id")
    if visitor_id is not None and not SAFE_ID.fullmatch(str(visitor_id)):
        raise EventError("invalid_visitor_id")
    consent = raw.get("consent_state")
    if consent not in contract["allowed_values"]["consent_state"]:
        raise EventError("invalid_consent_state")
    if visitor_id is not None and consent != "granted":
        raise EventError("persistent_id_without_consent")

    path = raw.get("path")
    if not isinstance(path, str) or not path.startswith("/") or "?" in path or "#" in path:
        raise EventError("unsafe_path")
    uat = raw.get("uat")
    if uat is not None and uat not in uats:
        raise EventError("unknown_uat")
    channel = raw.get("source_channel")
    if channel is not None and channel not in contract["allowed_values"]["source_channel"]:
        raise EventError("unknown_source_channel")
    device = raw.get("device_class")
    if device is not None and device not in contract["allowed_values"]["device_class"]:
        raise EventError("unknown_device_class")
    article_id = raw.get("article_id")
    if article_id is not None and not SAFE_ARTICLE_ID.fullmatch(str(article_id)):
        raise EventError("invalid_article_id")
    campaign_id = raw.get("campaign_id")
    if campaign_id is not None and not SAFE_CAMPAIGN.fullmatch(str(campaign_id)):
        raise EventError("invalid_campaign_id")

    event = dict(raw)
    event["_parsed_time"] = parse_time(raw["occurred_at"])
    return event


def classify_segments(events_by_visitor: dict[str, list[dict[str, Any]]]) -> dict[str, int]:
    result = Counter()
    for events in events_by_visitor.values():
        active_days = {event["_parsed_time"].date() for event in events}
        reads = sum(event["event"] == "article_read" for event in events)
        briefs = sum(event["event"] == "brief_open" for event in events)
        if len(active_days) >= 8 or reads >= 20:
            result["news_lovers"] += 1
        elif briefs >= 3:
            result["daily_briefers"] += 1
        else:
            result["casual_users"] += 1
    return {segment: result[segment] for segment in ("news_lovers", "daily_briefers", "casual_users")}


def returning_count(events_by_visitor: dict[str, list[dict[str, Any]]], max_days: int) -> int:
    count = 0
    for events in events_by_visitor.values():
        days = sorted({event["_parsed_time"].date() for event in events})
        if any(0 < (later - earlier).days <= max_days for index, earlier in enumerate(days) for later in days[index + 1 :]):
            count += 1
    return count


def aggregate(raw_events: list[Any], contract: dict[str, Any] | None = None) -> dict[str, Any]:
    contract = contract or load_contract()
    uats = load_uats()
    valid: list[dict[str, Any]] = []
    rejected = Counter()
    seen_event_ids: set[str] = set()
    for raw in raw_events:
        try:
            event = validate_event(raw, contract, uats)
            if event["event_id"] in seen_event_ids:
                raise EventError("duplicate_event_id")
            seen_event_ids.add(event["event_id"])
            valid.append(event)
        except EventError as exc:
            rejected[str(exc)] += 1

    measured = [event for event in valid if event.get("visitor_id") and event["consent_state"] == "granted"]
    by_visitor: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_uat: dict[str, set[str]] = defaultdict(set)
    for event in measured:
        visitor_id = event["visitor_id"]
        by_visitor[visitor_id].append(event)
        if event.get("uat"):
            by_uat[event["uat"]].add(visitor_id)

    denominator = contract["county_reach_gate"]["denominator"]
    numerator = len(by_visitor)
    county_reach = {
        "status": "BLOCKED_DENOMINATOR" if denominator is None else "MEASURED_FIRST_PARTY_NOT_CERTIFIED",
        "numerator": numerator,
        "denominator": denominator,
        "ratio": None if denominator is None else numerator / denominator,
        "certified": False,
    }
    return {
        "schema_version": 1,
        "input_events": len(raw_events),
        "valid_events": len(valid),
        "rejected_events": sum(rejected.values()),
        "rejection_reasons": dict(sorted(rejected.items())),
        "unique_measured_visitors": numerator,
        "unique_sessions": len({event["session_id"] for event in valid}),
        "returning_7d": returning_count(by_visitor, 7),
        "returning_30d": returning_count(by_visitor, 30),
        "visitors_by_segment": classify_segments(by_visitor),
        "visitors_by_uat": {uat: len(visitors) for uat, visitors in sorted(by_uat.items())},
        "county_reach": county_reach,
        "note": "Rezultat first-party operațional, necertificat. Evenimentele brute nu sunt incluse în output.",
    }


def read_jsonl(path: Path) -> list[Any]:
    events: list[Any] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"invalid JSON on line {line_number}: {exc.msg}") from exc
    return events


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    aggregate_parser = subparsers.add_parser("aggregate")
    aggregate_parser.add_argument("input", type=Path)
    aggregate_parser.add_argument("output", type=Path)
    args = parser.parse_args()

    result = aggregate(read_jsonl(args.input))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"ANALYTICS PASS: {result['valid_events']} valid; {result['rejected_events']} rejected; County Reach={result['county_reach']['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
