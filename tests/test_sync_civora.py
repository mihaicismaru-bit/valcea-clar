import unittest

from scripts.sync_civora import _freshness_key, _normalize_story, _normalize_visual


class SyncCivoraTests(unittest.TestCase):
    def setUp(self):
        self.feed = {"generated_at": "2026-08-27T00:00:00Z"}

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

    def test_refuses_bodyless_story(self):
        story = {"id": "story-3", "headline": "Titlu", "paragraphs": []}
        with self.assertRaises(SystemExit):
            _normalize_story(story, 0, self.feed, {}, set())


if __name__ == "__main__":
    unittest.main()
