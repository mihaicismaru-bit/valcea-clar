import json
import unittest
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from scripts.reconcile_civora_currentness_events import reconcile_events
from scripts.sync_civora import _extract_runtime_archive_story, _fetch_feed, _freshness_key, _normalize_story, _normalize_visual
from scripts.check_civora_projection_ready import validate as validate_projection_ready


class SyncCivoraTests(unittest.TestCase):
    def setUp(self):
        self.feed = {"generated_at": "2026-08-27T00:00:00Z"}

    def test_empty_canonical_feed_is_valid_zero_news_state(self):
        empty = {
            "canonical_domain": "valceaclar.ro",
            "publication_model": "continuous_story_first",
            "generated_at": "2026-10-09T00:00:00Z",
            "stories": [],
        }
        with patch("scripts.sync_civora._fetch_json", return_value=empty):
            self.assertEqual(_fetch_feed()["stories"], [])

    def test_projection_readiness_accepts_zero_current_feed(self):
        feed = {
            "canonical_domain": "valceaclar.ro",
            "publication_model": "continuous_story_first",
            "generated_at": "2026-10-09T00:00:00Z",
            "stories": [],
        }
        result = validate_projection_ready(
            feed,
            {"live_story_count": 3, "story_ids": ["archive-story"]},
            {"stories": []},
        )
        self.assertEqual(result["story_count"], 0)

    def test_build_source_does_not_backfill_archive_when_current_ids_explicitly_empty(self):
        from pathlib import Path
        source = Path("scripts/build.py").read_text(encoding="utf-8")
        self.assertIn("if not current_articles and 'current_story_ids' not in article_payload:", source)
        self.assertIn('data-current-story-count="0"', source)

    def test_freshness_beats_legacy_priority(self):
        older = {"id": "old", "priority": 100, "first_published_at": "2026-08-21T12:00:00+03:00"}
        newer = {"id": "new", "priority": 10, "first_published_at": "2026-08-26T22:35:00+03:00"}
        ordered = sorted([older, newer], key=lambda row: _freshness_key(row, self.feed), reverse=True)
        self.assertEqual(ordered[0]["id"], "new")

    def test_canonical_rank_controls_public_priority(self):
        story = {
            "id": "story-1",
            "section": "ACTUALITATE",
            "priority": 7,
            "headline": "Titlu verificat",
            "dek": "Rezumat",
            "paragraphs": ["Corp verificat."],
            "sources": [{"name": "Sursă", "url": "https://example.com", "tier": "T1"}],
            "first_published_at": "2026-08-27T01:00:00+03:00",
        }
        row = _normalize_story(story, 3, self.feed, {}, set())
        self.assertEqual(row["priority"], 999997)
        self.assertEqual(row["source_priority"], 7)
        self.assertEqual(row["canonical_rank"], 3)
        self.assertEqual(row["canonical_source"], "CIVORA")

    def test_verified_civora_runtime_visual_becomes_build_mirror(self):
        visual = {
            "filename": "verified-context.jpg",
            "public_url": "https://valceaclar.ro/media/social/verified-context.jpg",
            "relative_url": "/media/social/verified-context.jpg",
            "source_url": "https://commons.wikimedia.org/wiki/File:Verified.jpg",
            "credit": "Example / Wikimedia Commons",
            "rights_basis": "creative_commons",
            "license_url": "https://creativecommons.org/licenses/by/4.0/",
            "editorial_note": "Imagine de context verificată.",
            "contextual_archive": True,
            "synthetic": False,
            "provenance_status": "VERIFIED",
        }
        row = _normalize_visual("story-visual", visual)
        self.assertIsNotNone(row)
        self.assertEqual(row["image"], "verified-context.jpg")
        self.assertEqual(
            row["image_fetch_url"],
            "https://raw.githubusercontent.com/mihaicismaru-bit/civora/main/valcea-clar/site/runtime/media/social/verified-context.jpg",
        )
        self.assertEqual(row["image_origin_url"], visual["public_url"])
        self.assertEqual(row["image_provenance_status"], "VERIFIED")

    def test_verified_external_visual_gets_deterministic_local_name(self):
        visual = {
            "public_url": "https://commons.wikimedia.org/wiki/Special:Redirect/file/Ora%C8%99ul_Brezoi.jpg",
            "source_url": "https://commons.wikimedia.org/wiki/File:Ora%C8%99ul_Brezoi.jpg",
            "credit": "Claudiupt / Wikimedia Commons — CC0",
            "rights_basis": "cc0",
            "synthetic": False,
            "provenance_status": "VERIFIED",
        }
        row = _normalize_visual("brezoi", visual)
        self.assertIsNotNone(row)
        self.assertTrue(row["image"].startswith("civora-"))
        self.assertTrue(row["image"].endswith(".jpg"))
        self.assertEqual(row["image_fetch_url"], visual["public_url"])

    def archive_projection(self, image, old=None):
        canonical = "https://valceaclar.ro/stiri/archive-photo/"
        news = {"@type": "NewsArticle", "url": canonical, "headline": "Titlu",
                "datePublished": "2026-09-20T12:00:00+03:00"}
        page = (f'<link rel="canonical" href="{canonical}">'
                f'<script type="application/ld+json">{json.dumps(news)}</script>'
                '<h1>Titlu</h1><div class="article-body"><p>Corp verificat.</p></div>'
                '<section class="article-sources"><a href="https://example.com/source">Sursă</a></section>')
        manifest = {"id": "archive-photo", "path": "/stiri/archive-photo/",
                    "canonical": canonical, "public_ux_authorized": True,
                    "structured_data_type": "NewsArticle", "image": image}
        with patch("scripts.sync_civora._fetch_text", return_value=page):
            return _extract_runtime_archive_story(manifest, 9, old or {}, {"local.webp"})

    def test_archive_projects_current_verified_manifest_photo_before_legacy_local(self):
        visual = {"public_url": "https://example.com/verified.jpg", "provenance_status": "VERIFIED",
                  "source_url": "https://example.com/source", "credit": "Credit", "rights_basis": "licensed",
                  "contextual_archive": True, "editorial_note": "Foto de context; nu documentează evenimentul."}
        row = self.archive_projection(visual, {"archive-photo": {"image": "local.webp"}})
        self.assertEqual(row["image_origin_url"], visual["public_url"])
        self.assertEqual(row["image_fetch_url"], visual["public_url"])
        self.assertEqual(row["image_provenance_status"], "VERIFIED")
        self.assertEqual(row["image_caption"], visual["editorial_note"])
        self.assertTrue(row["archive_only"])
        self.assertTrue(row["image_site_eligible"])
        self.assertEqual(row["paragraphs"], ["Corp verificat."])

    def test_archive_unverified_or_missing_visual_keeps_existing_fallback(self):
        for visual in (None, {"public_url": "https://example.com/held.jpg", "provenance_status": "HOLD"}):
            with self.subTest(visual=visual):
                self.assertIsNone(self.archive_projection(visual)["image"])
                row = self.archive_projection(visual, {"archive-photo": {"image": "local.webp"}})
                self.assertEqual(row["image"], "local.webp")
                self.assertNotIn("image_fetch_url", row)

    def test_archive_social_card_remains_ineligible(self):
        row = self.archive_projection({"public_url": "https://example.com/card.jpg",
                                      "provenance_status": "VERIFIED", "rights_basis": "original_editorial_layout"})
        self.assertFalse(row["image_site_eligible"])

    def test_social_editorial_card_is_not_site_eligible(self):
        visual = {
            "filename": "story-og.jpg",
            "public_url": "https://valceaclar.ro/media/social/editorial/story-og.jpg",
            "relative_url": "/media/social/editorial/story-og.jpg",
            "credit": "VÂLCEA CLAR — card editorial",
            "rights_basis": "original_editorial_layout",
            "synthetic": False,
            "provenance_status": "VERIFIED",
        }
        row = _normalize_visual("story-card", visual)
        self.assertIsNotNone(row)
        self.assertFalse(row["image_site_eligible"])
        self.assertEqual(row["image_asset_role"], "social_card")

    def test_verified_ai_illustration_can_be_site_visual_when_not_real_scene(self):
        visual = {
            "filename": "story-ai.jpg",
            "public_url": "https://valceaclar.ro/media/editorial/story-ai.jpg",
            "relative_url": "/media/editorial/story-ai.jpg",
            "credit": "VÂLCEA CLAR — ilustrație AI",
            "rights_basis": "ai_generated_editorial",
            "synthetic": True,
            "depicts_real_scene": False,
            "provenance_status": "VERIFIED",
        }
        row = _normalize_visual("story-ai", visual)
        self.assertIsNotNone(row)
        self.assertTrue(row["image_site_eligible"])
        self.assertTrue(row["image_synthetic"])
        self.assertFalse(row["image_depicts_real_scene"])
        self.assertEqual(row["image_asset_role"], "site_visual")

    def test_synthetic_visual_without_false_real_scene_flag_is_not_site_eligible(self):
        visual = {
            "filename": "story-ai-unsafe.jpg",
            "public_url": "https://valceaclar.ro/media/editorial/story-ai-unsafe.jpg",
            "synthetic": True,
            "provenance_status": "VERIFIED",
        }
        row = _normalize_visual("story-ai-unsafe", visual)
        self.assertIsNotNone(row)
        self.assertFalse(row["image_site_eligible"])

    def test_unverified_visual_does_not_override_registered_local_media(self):
        story = {
            "id": "story-2",
            "headline": "Titlu",
            "dek": "Rezumat",
            "paragraphs": ["Corp."],
            "visual": {
                "filename": "remote.jpg",
                "public_url": "https://example.com/remote.jpg",
                "editorial_note": "Remote",
                "provenance_status": "HOLD",
            },
        }
        old = {"story-2": {"image": "local.webp", "image_caption": "Local"}}
        row = _normalize_story(story, 0, self.feed, old, {"local.webp"})
        self.assertEqual(row["image"], "local.webp")
        self.assertEqual(row["image_caption"], "Local")
        self.assertNotIn("image_fetch_url", row)

    def test_public_event_reconcile_drops_expired_legacy_rows(self):
        tz = ZoneInfo("Europe/Bucharest")
        now = datetime(2026, 9, 26, 19, 15, tzinfo=tz)
        existing = {
            "events": [
                {
                    "id": "expired-24-sep",
                    "start": "2026-09-24T19:00:00+03:00",
                    "event_start": "2026-09-24",
                    "start_time": "19:00",
                    "title": "Eveniment expirat",
                    "locality": "Râmnicu Vâlcea",
                    "checked_at": "2026-09-24T12:00:00+03:00",
                    "status": "scheduled",
                },
                {
                    "id": "future-27-sep",
                    "start": "2026-09-27T11:00:00+03:00",
                    "event_start": "2026-09-27",
                    "start_time": "11:00",
                    "title": "Eveniment viitor",
                    "locality": "Mălaia",
                    "checked_at": "2026-09-26T09:00:00+03:00",
                    "status": "scheduled",
                },
            ]
        }
        reconciled, _ = reconcile_events(existing, {"events": []}, now)
        ids = [row["id"] for row in reconciled["events"]]
        self.assertNotIn("expired-24-sep", ids)
        self.assertIn("future-27-sep", ids)

    def test_refuses_bodyless_story(self):
        story = {"id": "story-3", "headline": "Titlu", "paragraphs": []}
        with self.assertRaises(SystemExit):
            _normalize_story(story, 0, self.feed, {}, set())


if __name__ == "__main__":
    unittest.main()
