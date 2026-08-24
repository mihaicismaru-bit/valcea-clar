#!/usr/bin/env python3
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import newsroom as nr  # noqa: E402

_ORIGINAL_ITEMS = nr.items


def bounded_items(src, text):
    rows = _ORIGINAL_ITEMS(src, text)
    if src.get("structured_detail_adapter") != "cj_agenda":
        return rows

    today = datetime.now(ZoneInfo("Europe/Bucharest")).date()
    max_age = int(src.get("max_age_days") or 21)
    fresh = []
    for title, url in rows:
        d = nr.extract_date({"url": url}, title)
        if d is None:
            continue
        age = (today - d).days
        if -45 <= age <= max_age:
            label = title
            if title.strip().lower() == "detalii":
                label = f"Ședința CJ Vâlcea din {d.strftime('%d.%m.%Y')}"
            fresh.append((label, url))
    return fresh[:8]


def main() -> int:
    nr.items = bounded_items
    nr.cycle(False)
    return nr.verify()


if __name__ == "__main__":
    raise SystemExit(main())
