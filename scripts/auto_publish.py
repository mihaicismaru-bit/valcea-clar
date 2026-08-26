#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
NR = ROOT / "newsroom"
CONTENT = ROOT / "content"
OUT = NR / "output"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def authority_errors():
    cfg = load(NR / "publication.json")
    core = load(NR / "policy.json")
    sources = {s["id"]: s for s in load(NR / "sources.json")["sources"]}
    errs = []
    if cfg.get("mode") != "live" or cfg.get("auto_publish") is not True:
        errs.append("auto-publication authority is not live")
    if cfg.get("authority") != "OWNER_APPROVED_AUTO_PUBLICATION":
        errs.append("owner authority marker missing")
    # Defense in depth: discovery/core remains candidate-only. Only this promoter can go live.
    if core.get("publication_mode") != "candidate_only" or core.get("auto_publish") is not False:
        errs.append("candidate core must remain locked")
    allowed_tiers = set(cfg.get("allowed_tiers", []))
    for source_id in cfg.get("allowed_source_ids", []):
        src = sources.get(source_id)
        if not src:
            errs.append(f"unknown allowed source: {source_id}")
            continue
        if src.get("tier") not in allowed_tiers:
            errs.append(f"source tier not allowed: {source_id}")
        if not src.get("structured_detail_adapter"):
            errs.append(f"source lacks structured detail adapter: {source_id}")
    if int(cfg.get("max_per_cycle", 0)) < 1:
        errs.append("max_per_cycle must be positive")
    return errs


def eligible(story, cfg):
    candidate = story.get("source_candidate") or {}
    if story.get("status") != cfg.get("require_candidate_status"):
        return False, "candidate_status"
    if candidate.get("decision") != cfg.get("require_candidate_decision"):
        return False, "candidate_decision"
    if candidate.get("tier") not in set(cfg.get("allowed_tiers", [])):
        return False, "tier"
    if candidate.get("source_id") not in set(cfg.get("allowed_source_ids", [])):
        return False, "source"
    if cfg.get("require_zero_risks") and candidate.get("risks"):
        return False, "risk"
    sources = story.get("sources") or []
    if not sources or any(not s.get("url") for s in sources):
        return False, "source_url"
    return True, None


def to_article(story, cfg, published_at):
    article = {
        "id": story["id"],
        "section": story["section"],
        "priority": int(cfg.get("default_priority", 100)),
        "headline": story["headline"],
        "dek": story["dek"],
        "paragraphs": story["paragraphs"],
        "sources": [{"name": s["name"], "url": s["url"]} for s in story["sources"]],
        "published": published_at,
        "image": story.get("image"),
        "publication_mode": "AUTO_PUBLISHED",
        "automation": {
            "source_id": story.get("source_candidate", {}).get("source_id"),
            "source_tier": story.get("source_candidate", {}).get("tier"),
            "candidate_score": story.get("source_candidate", {}).get("score"),
            "authority": cfg.get("authority"),
        },
    }
    if article.get("image"):
        article["image_caption"] = "Imagine de context din arhiva VÂLCEA CLAR; nu surprinde în mod necesar evenimentul relatat."
    return article


def select(stories, existing_ids, cfg):
    selected = []
    skipped = []
    for story in stories:
        if story.get("id") in existing_ids:
            skipped.append({"id": story.get("id"), "reason": "already_published"})
            continue
        ok, reason = eligible(story, cfg)
        if not ok:
            skipped.append({"id": story.get("id"), "reason": reason})
            continue
        selected.append(story)
        if len(selected) >= int(cfg.get("max_per_cycle", 3)):
            break
    return selected, skipped


def sync_queue(stories, existing_ids, published_ids, cfg):
    queue = load(OUT / "queue.json")
    story_by_id = {story.get("id"): story for story in stories}
    # The promoter may annotate rows, but it must never unlock candidate-core.
    queue["status"] = "LOCKED_CANDIDATE_ONLY"
    for row in queue.get("queue", []):
        ident = row.get("id")
        if ident in published_ids or ident in existing_ids:
            row["status"] = "PUBLISHED_AUTO"
            continue
        story = story_by_id.get(ident)
        ok, _ = eligible(story, cfg) if story else (False, "missing_story")
        row["status"] = "AUTO_PUBLISH_READY" if ok else "CANDIDATE_ONLY"
    dump(OUT / "queue.json", queue)


def run(dry_run=False):
    errs = authority_errors()
    if errs:
        raise SystemExit("AUTO PUBLISH VERIFY FAIL\n- " + "\n- ".join(errs))

    cfg = load(NR / "publication.json")
    story_doc = load(OUT / "stories.json")
    stories = story_doc.get("stories", [])
    article_doc = load(CONTENT / "articles.json")
    existing = {a["id"] for a in article_doc.get("articles", [])}
    selected, skipped = select(stories, existing, cfg)
    now = datetime.now(ZoneInfo("Europe/Bucharest")).isoformat(timespec="seconds")
    articles = [to_article(s, cfg, now) for s in selected]

    report = {
        "status": "DRY_RUN" if dry_run else "AUTO_PUBLISH_ACTIVE",
        "authority": cfg.get("authority"),
        "checked_local": now,
        "selected": [{"id": a["id"], "headline": a["headline"]} for a in articles],
        "published": [] if dry_run else [{"id": a["id"], "headline": a["headline"]} for a in articles],
        "skipped": skipped,
    }

    if not dry_run:
        published_ids = {a["id"] for a in articles}
        if articles:
            article_doc["updated_local"] = now
            article_doc["articles"] = articles + article_doc.get("articles", [])
            dump(CONTENT / "articles.json", article_doc)
        sync_queue(stories, existing, published_ids, cfg)

    dump(OUT / "publish.json", report)
    print(f"AUTO PUBLISH {'DRY RUN' if dry_run else 'PASS'}: {len(articles)} new article(s); authority={cfg.get('authority')}")
    return len(articles)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.verify:
        errs = authority_errors()
        if errs:
            print("AUTO PUBLISH VERIFY FAIL\n- " + "\n- ".join(errs))
            raise SystemExit(1)
        print("AUTO PUBLISH VERIFY PASS: candidate core locked; live promoter owner-authorized; T1 structured sources only.")
        return
    run(args.dry_run)


if __name__ == "__main__":
    main()
