import unittest

from scripts.sync_civora import _freshness_key, _normalize_story


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

    def test_preserves_only_registered_local_media(self):
        story = {
            "id": "story-2",
            "headline": "Titlu",
            "dek": "Rezumat",
            "paragraphs": ["Corp."],
            "visual": {"filename": "remote.jpg", "editorial_note": "Remote"},
        }
        old = {"story-2": {"image": "local.webp", "image_caption": "Local"}}
        row = _normalize_story(story, 0, self.feed, old, {"local.webp"})
        self.assertEqual(row["image"], "local.webp")
        self.assertEqual(row["image_caption"], "Local")

    def test_refuses_bodyless_story(self):
        story = {"id": "story-3", "headline": "Titlu", "paragraphs": []}
        with self.assertRaises(SystemExit):
            _normalize_story(story, 0, self.feed, {}, set())


if __name__ == "__main__":
    unittest.main()
