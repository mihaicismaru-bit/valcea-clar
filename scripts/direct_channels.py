#!/usr/bin/env python3
"""Validate direct-channel preferences and produce a no-send delivery plan."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "strategy" / "direct_channel_contract.json"
UAT_PATH = ROOT / "strategy" / "source_coverage_matrix.json"
SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{8,100}$")
SAFE_URL = re.compile(r"^https://[^\s]+$")


class ContractError(ValueError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_contract() -> dict[str, Any]:
    return load_json(CONTRACT_PATH)


def load_uats() -> set[str]:
    matrix = load_json(UAT_PATH)
    return {entry["name"] for entry in matrix["uats"]}


def parse_time(value: Any, reason: str) -> datetime:
    if not isinstance(value, str):
        raise ContractError(reason)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError(reason) from exc
    if parsed.tzinfo is None:
        raise ContractError(reason)
    return parsed


def reject_forbidden(raw: Any, contract: dict[str, Any]) -> None:
    if not isinstance(raw, dict):
        raise ContractError("not_object")
    if set(raw).intersection(contract["privacy"]["forbidden_fields"]):
        raise ContractError("forbidden_personal_field")


def validate_subscription(raw: Any, contract: dict[str, Any], uats: set[str]) -> dict[str, Any]:
    reject_forbidden(raw, contract)
    missing = [field for field in contract["required_subscription_fields"] if raw.get(field) in (None, "", [])]
    if missing:
        raise ContractError("subscription_missing_required")
    if raw["contract_version"] != contract["schema_version"]:
        raise ContractError("stale_contract_version")
    if raw["channel"] not in contract["channels"]:
        raise ContractError("unknown_channel")
    if raw["consent_state"] != "granted":
        raise ContractError("consent_not_granted")
    if not SAFE_ID.fullmatch(str(raw["subscriber_id"])) or not SAFE_ID.fullmatch(str(raw["destination_ref"])):
        raise ContractError("unsafe_subscription_id")
    parse_time(raw["consented_at"], "invalid_consented_at")
    if not isinstance(raw["localities"], list) or not isinstance(raw["topics"], list):
        raise ContractError("subscription_scope_not_list")
    county = contract["locality_scope"]["county_value"]
    if any(locality != county and locality not in uats for locality in raw["localities"]):
        raise ContractError("unknown_locality")
    allowed_topics = set(contract["channels"][raw["channel"]]["topics"])
    if not set(raw["topics"]).issubset(allowed_topics):
        raise ContractError("topic_not_allowed_for_channel")
    return dict(raw)


def validate_message(raw: Any, contract: dict[str, Any], uats: set[str]) -> dict[str, Any]:
    reject_forbidden(raw, contract)
    missing = [field for field in contract["required_message_fields"] if raw.get(field) in (None, "")]
    if missing:
        raise ContractError("message_missing_required")
    if raw["channel"] not in contract["channels"]:
        raise ContractError("unknown_channel")
    if raw["topic"] not in contract["channels"][raw["channel"]]["topics"]:
        raise ContractError("topic_not_allowed_for_channel")
    for key in ("message_id", "event_id"):
        if not SAFE_ID.fullmatch(str(raw[key])):
            raise ContractError("unsafe_message_id")
    if raw["publication_status"] != contract["authority"]["required_publication_status"]:
        raise ContractError("content_not_published_verified")
    if raw["authorized_for_distribution"] is not True:
        raise ContractError("distribution_not_authorized")
    if raw["source_tier"] not in ("T1", "T2"):
        raise ContractError("unknown_source_tier")
    if raw["priority"] not in ("normal", "high", "critical"):
        raise ContractError("unknown_priority")
    if not SAFE_URL.fullmatch(str(raw["source_url"])):
        raise ContractError("unsafe_source_url")
    uat = raw.get("uat")
    if uat is not None and uat not in uats:
        raise ContractError("unknown_locality")
    scheduled = parse_time(raw["scheduled_at"], "invalid_scheduled_at")
    expires = parse_time(raw["expires_at"], "invalid_expires_at")
    if expires <= scheduled:
        raise ContractError("expired_before_schedule")
    result = dict(raw)
    result["_scheduled"] = scheduled
    result["_expires"] = expires
    return result


def in_quiet_hours(when: datetime, contract: dict[str, Any]) -> bool:
    quiet = contract["quiet_hours"]
    local = when.astimezone(ZoneInfo(quiet["timezone"]))
    return local.hour >= quiet["start_hour"] or local.hour < quiet["end_hour"]


def may_bypass_quiet_hours(message: dict[str, Any]) -> bool:
    return (
        message["topic"] == "urgent_alert"
        and message["priority"] == "critical"
        and message["source_tier"] == "T1"
        and message["authorized_for_distribution"] is True
        and message["_expires"] > message["_scheduled"]
    )


def scope_matches(subscription: dict[str, Any], message: dict[str, Any], contract: dict[str, Any]) -> bool:
    if subscription["channel"] != message["channel"] or message["topic"] not in subscription["topics"]:
        return False
    if message.get("uat") is None:
        return contract["locality_scope"]["county_value"] in subscription["localities"]
    return message["uat"] in subscription["localities"] or contract["locality_scope"]["county_value"] in subscription["localities"]


def count_recent(records: list[dict[str, Any]], scheduled: datetime, window: timedelta, channel: str | None = None) -> int:
    return sum(
        scheduled - window < record["sent_at"] <= scheduled
        and (channel is None or record["channel"] == channel)
        for record in records
    )


def plan_deliveries(
    raw_subscriptions: list[Any], raw_messages: list[Any], raw_history: list[Any], contract: dict[str, Any] | None = None
) -> dict[str, Any]:
    contract = contract or load_contract()
    uats = load_uats()
    rejected = Counter()
    subscriptions = []
    for raw in raw_subscriptions:
        try:
            subscriptions.append(validate_subscription(raw, contract, uats))
        except ContractError as exc:
            rejected[f"subscription:{exc}"] += 1
    messages = []
    seen_message_ids: set[str] = set()
    for raw in raw_messages:
        try:
            message = validate_message(raw, contract, uats)
            if message["message_id"] in seen_message_ids:
                raise ContractError("duplicate_message_id")
            seen_message_ids.add(message["message_id"])
            messages.append(message)
        except ContractError as exc:
            rejected[f"message:{exc}"] += 1

    history: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for raw in raw_history:
        try:
            reject_forbidden(raw, contract)
            if not SAFE_ID.fullmatch(str(raw.get("subscriber_id", ""))) or raw.get("channel") not in contract["channels"]:
                raise ContractError("invalid_history")
            history[raw["subscriber_id"]].append({"channel": raw["channel"], "sent_at": parse_time(raw.get("sent_at"), "invalid_history")})
        except ContractError as exc:
            rejected[f"history:{exc}"] += 1

    planned: list[dict[str, str]] = []
    holds = Counter()
    channel_caps = contract["channels"]
    global_caps = contract["global_frequency_cap"]
    for message in sorted(messages, key=lambda item: (item["_scheduled"], item["message_id"])):
        for subscription in subscriptions:
            if not scope_matches(subscription, message, contract):
                continue
            if in_quiet_hours(message["_scheduled"], contract) and not may_bypass_quiet_hours(message):
                holds["quiet_hours"] += 1
                continue
            records = history[subscription["subscriber_id"]]
            caps = channel_caps[message["channel"]]
            if count_recent(records, message["_scheduled"], timedelta(hours=24), message["channel"]) >= caps["max_per_24h"]:
                holds["channel_24h_cap"] += 1
                continue
            if count_recent(records, message["_scheduled"], timedelta(days=7), message["channel"]) >= caps["max_per_7d"]:
                holds["channel_7d_cap"] += 1
                continue
            if count_recent(records, message["_scheduled"], timedelta(hours=24)) >= global_caps["max_per_24h"]:
                holds["global_24h_cap"] += 1
                continue
            if count_recent(records, message["_scheduled"], timedelta(days=7)) >= global_caps["max_per_7d"]:
                holds["global_7d_cap"] += 1
                continue
            planned.append({
                "subscriber_id": subscription["subscriber_id"],
                "message_id": message["message_id"],
                "channel": message["channel"],
                "scheduled_at": message["scheduled_at"],
            })
            records.append({"channel": message["channel"], "sent_at": message["_scheduled"]})

    return {
        "schema_version": 1,
        "status": "CANDIDATE_NO_SEND",
        "sending_allowed": False,
        "valid_subscriptions": len(subscriptions),
        "valid_messages": len(messages),
        "planned_count": len(planned),
        "planned": planned,
        "holds": dict(sorted(holds.items())),
        "rejected": dict(sorted(rejected.items())),
        "note": "Planul conține numai identificatori opaci și nu expediază mesaje. Destination refs și datele personale nu apar în output.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("subscriptions", type=Path)
    parser.add_argument("messages", type=Path)
    parser.add_argument("history", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = plan_deliveries(load_json(args.subscriptions), load_json(args.messages), load_json(args.history))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"DIRECT CHANNEL PASS: {result['planned_count']} planned; sending_allowed=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
