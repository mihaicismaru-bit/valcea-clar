import json, unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class MarketIntelligenceTests(unittest.TestCase):
 def setUp(self):
  self.data = json.loads((ROOT / 'strategy/market_intelligence_valcea.json').read_text(encoding='utf-8'))

 def test_baseline_is_dated_bounded_and_not_an_audience_claim(self):
  datetime.fromisoformat(self.data['checked_local'])
  self.assertEqual(len(self.data['competitors']), 3)
  self.assertEqual(len({row['id'] for row in self.data['competitors']}), 3)
  self.assertIn('Nu este un clasament de audiență', self.data['scope'])

 def test_competitors_have_https_evidence_and_all_dimensions(self):
  required = {'update_cadence', 'geographic_breadth', 'utility_coverage', 'format_mix', 'direct_channels', 'trust_signals'}
  for row in self.data['competitors']:
   self.assertTrue(row['homepage'].startswith('https://'))
   self.assertTrue(row['feed'].startswith('https://'))
   self.assertEqual(set(row['dimensions']), required)
   self.assertGreaterEqual(row['feed_items_24h'], 0)
   for dimension in row['dimensions'].values():
    self.assertIn(dimension['score_0_3'], range(4))
    self.assertTrue(dimension['observation'])
    self.assertTrue(dimension['evidence'])
    self.assertTrue(all(url.startswith('https://') for url in dimension['evidence']))

 def test_absence_is_scoped_to_checked_surfaces(self):
  raw = json.dumps(self.data, ensure_ascii=False).lower()
  self.assertIn('neobservat, nu ca inexistent', raw)
  self.assertNotIn('nu există politică de corecții', raw)

 def test_experiments_are_ranked_and_evaluated(self):
  rows = self.data['ranked_experiments']
  self.assertEqual([row['rank'] for row in rows], list(range(1, len(rows) + 1)))
  required = {'rank', 'id', 'hypothesis', 'impact', 'editorial_risk', 'cost', 'effort', 'dependencies', 'measurability', 'success_signal'}
  for row in rows:
   self.assertEqual(set(row), required)
   self.assertTrue(row['dependencies'])
   self.assertTrue(row['success_signal'])
  self.assertEqual(rows[0]['id'], 'trust_verification_corrections')
  self.assertEqual(rows[0]['editorial_risk'], 'low')

 def test_no_invented_reach_or_certification(self):
  forbidden = {'audience_reach', 'county_reach_percent', 'certified_audience', 'unique_users'}
  self.assertTrue(forbidden.isdisjoint(self.data))
  raw = json.dumps(self.data, ensure_ascii=False).lower()
  self.assertNotIn('audiență certificată:', raw)
  self.assertNotIn('utilizatori unici:', raw)


if __name__ == '__main__':
 unittest.main()
