import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("analytics", ROOT / "scripts" / "analytics.py")
analytics = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(analytics)


class AnalyticsContractTests(unittest.TestCase):
    def setUp(self):
        fixture = ROOT / "tests" / "fixtures" / "analytics_events.jsonl"
        self.events = [json.loads(line) for line in fixture.read_text(encoding="utf-8").splitlines()]

    def test_fixture_aggregation_is_deterministic_and_not_certified(self):
        result = analytics.aggregate(self.events)
        self.assertEqual(result["valid_events"], 7)
        self.assertEqual(result["rejected_events"], 0)
        self.assertEqual(result["unique_measured_visitors"], 2)
        self.assertEqual(result["unique_sessions"], 7)
        self.assertEqual(result["returning_7d"], 1)
        self.assertEqual(result["returning_30d"], 2)
        self.assertEqual(result["visitors_by_segment"], {"news_lovers": 0, "daily_briefers": 1, "casual_users": 1})
        self.assertEqual(result["visitors_by_uat"], {"Călimănești": 1, "Râmnicu Vâlcea": 1})
        self.assertEqual(result["county_reach"]["status"], "BLOCKED_DENOMINATOR")
        self.assertIsNone(result["county_reach"]["ratio"])
        self.assertFalse(result["county_reach"]["certified"])

    def test_forbidden_personal_field_is_rejected(self):
        event = copy.deepcopy(self.events[0])
        event["email"] = "reader@example.invalid"
        result = analytics.aggregate([event])
        self.assertEqual(result["rejection_reasons"], {"forbidden_field": 1})

    def test_unknown_uat_is_rejected(self):
        event = copy.deepcopy(self.events[0])
        event["uat"] = "Localitate inventată"
        result = analytics.aggregate([event])
        self.assertEqual(result["rejection_reasons"], {"unknown_uat": 1})

    def test_query_string_is_rejected(self):
        event = copy.deepcopy(self.events[0])
        event["path"] = "/stiri?email=secret"
        result = analytics.aggregate([event])
        self.assertEqual(result["rejection_reasons"], {"unsafe_path": 1})

    def test_persistent_identifier_requires_consent(self):
        event = copy.deepcopy(self.events[0])
        event["consent_state"] = "denied"
        result = analytics.aggregate([event])
        self.assertEqual(result["rejection_reasons"], {"persistent_id_without_consent": 1})

    def test_duplicate_event_id_is_rejected(self):
        result = analytics.aggregate([self.events[0], copy.deepcopy(self.events[0])])
        self.assertEqual(result["valid_events"], 1)
        self.assertEqual(result["rejection_reasons"], {"duplicate_event_id": 1})


if __name__ == "__main__":
    unittest.main()
