import copy
import importlib.util
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("direct_channels", ROOT / "scripts" / "direct_channels.py")
direct_channels = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(direct_channels)


class DirectChannelContractTests(unittest.TestCase):
    def setUp(self):
        self.subscription = {
            "subscriber_id": "subscriber_alpha",
            "destination_ref": "provider_ref_alpha",
            "channel": "web_push",
            "consent_state": "granted",
            "consented_at": "2026-08-25T12:00:00+03:00",
            "contract_version": 1,
            "localities": ["Călimănești"],
            "topics": ["utility_alert", "urgent_alert"]
        }
        self.message = {
            "message_id": "message_alpha_01",
            "event_id": "event_alpha_001",
            "channel": "web_push",
            "topic": "utility_alert",
            "publication_status": "PUBLISHED_VERIFIED",
            "source_tier": "T1",
            "authorized_for_distribution": True,
            "scheduled_at": "2026-08-26T10:00:00+03:00",
            "expires_at": "2026-08-26T18:00:00+03:00",
            "priority": "high",
            "source_url": "https://example.invalid/official",
            "uat": "Călimănești"
        }

    def plan(self, subscriptions=None, messages=None, history=None):
        return direct_channels.plan_deliveries(
            subscriptions if subscriptions is not None else [self.subscription],
            messages if messages is not None else [self.message],
            history if history is not None else []
        )

    def test_valid_opt_in_and_locality_create_no_send_plan(self):
        result = self.plan()
        self.assertEqual(result["planned_count"], 1)
        self.assertFalse(result["sending_allowed"])
        self.assertNotIn("destination_ref", result["planned"][0])

    def test_consent_is_channel_specific_and_fail_closed(self):
        subscription = copy.deepcopy(self.subscription)
        subscription["consent_state"] = "denied"
        result = self.plan(subscriptions=[subscription])
        self.assertEqual(result["planned_count"], 0)
        self.assertEqual(result["rejected"], {"subscription:consent_not_granted": 1})

    def test_raw_destination_is_rejected(self):
        subscription = copy.deepcopy(self.subscription)
        subscription["phone"] = "+40000000000"
        result = self.plan(subscriptions=[subscription])
        self.assertEqual(result["rejected"], {"subscription:forbidden_personal_field": 1})

    def test_unknown_locality_is_rejected(self):
        subscription = copy.deepcopy(self.subscription)
        subscription["localities"] = ["UAT inventat"]
        result = self.plan(subscriptions=[subscription])
        self.assertEqual(result["rejected"], {"subscription:unknown_locality": 1})

    def test_unpublished_message_is_rejected(self):
        message = copy.deepcopy(self.message)
        message["publication_status"] = "CANDIDATE"
        result = self.plan(messages=[message])
        self.assertEqual(result["rejected"], {"message:content_not_published_verified": 1})

    def test_quiet_hours_hold_normal_message(self):
        message = copy.deepcopy(self.message)
        message["scheduled_at"] = "2026-08-26T23:00:00+03:00"
        message["expires_at"] = "2026-08-27T12:00:00+03:00"
        result = self.plan(messages=[message])
        self.assertEqual(result["holds"], {"quiet_hours": 1})

    def test_critical_t1_urgent_alert_may_bypass_quiet_hours(self):
        message = copy.deepcopy(self.message)
        message.update({
            "topic": "urgent_alert",
            "priority": "critical",
            "scheduled_at": "2026-08-26T23:00:00+03:00",
            "expires_at": "2026-08-27T02:00:00+03:00"
        })
        result = self.plan(messages=[message])
        self.assertEqual(result["planned_count"], 1)

    def test_channel_frequency_cap_holds_excess(self):
        scheduled = datetime.fromisoformat(self.message["scheduled_at"])
        history = [
            {"subscriber_id": "subscriber_alpha", "channel": "web_push", "sent_at": (scheduled - timedelta(hours=hours)).isoformat()}
            for hours in (1, 2, 3)
        ]
        result = self.plan(history=history)
        self.assertEqual(result["holds"], {"channel_24h_cap": 1})

    def test_cross_channel_topic_mismatch_does_not_plan(self):
        message = copy.deepcopy(self.message)
        message["channel"] = "newsletter"
        message["topic"] = "morning_brief"
        result = self.plan(messages=[message])
        self.assertEqual(result["planned_count"], 0)


if __name__ == "__main__":
    unittest.main()
