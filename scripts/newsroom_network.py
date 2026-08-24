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
_ORIGINAL_CJ_STORY = nr.cj_story


def bounded_items(src, text):
    rows = _ORIGINAL_ITEMS(src, text)
    if src.get("structured_detail_adapter") != "cj_agenda":
        return rows

    today = datetime.now(ZoneInfo("Europe/Bucharest")).date()
    fresh = []
    for title, url in rows:
        d = nr.extract_date({"url": url}, title)
        if d is None:
            continue
        age = (today - d).days
        # Agenda copy is valid only immediately around or before the meeting.
        # Past meetings require a different adopted-decision adapter, not future-tense agenda copy.
        if -45 <= age <= 1:
            label = title
            if title.strip().lower() == "detalii":
                label = f"Ședința CJ Vâlcea din {d.strftime('%d.%m.%Y')}"
            fresh.append((label, url))
    return fresh[:8]


def cj_story_with_safe_punctuation(candidate, detail):
    story = _ORIGINAL_CJ_STORY(candidate, detail)
    story["headline"] = story.get("headline", "").replace(
        "pe ordinea de zi. proiecte", "pe ordinea de zi, proiecte"
    )
    return story


def main() -> int:
    nr.items = bounded_items
    nr.cj_story = cj_story_with_safe_punctuation
    nr.cycle(False)
    return nr.verify()


if __name__ == "__main__":
    raise SystemExit(main())
