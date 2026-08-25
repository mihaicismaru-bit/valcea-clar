import json,unittest
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class StrategyCoverageTests(unittest.TestCase):
 def test_all_valcea_uats_are_unique_and_typed(self):
  d=json.loads((ROOT/'strategy/source_coverage_matrix.json').read_text(encoding='utf-8')); rows=d['uats']; counts=Counter(x['type'] for x in rows)
  self.assertEqual(len(rows),89); self.assertEqual(len({x['name'] for x in rows}),89); self.assertEqual(counts,{'municipality':2,'town':9,'commune':78})
 def test_every_uat_profile_covers_every_need(self):
  d=json.loads((ROOT/'strategy/source_coverage_matrix.json').read_text(encoding='utf-8')); needs={x['id'] for x in d['needs']}
  for row in d['uats']:
   self.assertIn(row['profile'],d['coverage_profiles']); self.assertEqual(set(d['coverage_profiles'][row['profile']]),needs)
 def test_selected_electricity_source_is_candidate_only(self):
  sources=json.loads((ROOT/'newsroom/sources.json').read_text(encoding='utf-8'))['sources']; src=next(x for x in sources if x['id']=='distributie_oltenia_valcea_planned')
  self.assertEqual(src['publication_scope'],'candidate_only'); pub=json.loads((ROOT/'newsroom/publication.json').read_text(encoding='utf-8')); self.assertNotIn(src['id'],pub['allowed_source_ids'])
 def test_growth_inventory_tracks_utility_calendar(self):
  methods=json.loads((ROOT/'strategy/growth_inventory.json').read_text(encoding='utf-8'))['methods']; row=next(x for x in methods if x['id']=='planned_utility_calendar')
  self.assertEqual(row['status'],'TESTAT'); self.assertEqual(row['editorial_risk'],'low'); self.assertIn('10/10',row['evidence'])
 def test_tomorrow_locality_brief_is_measurable_and_not_live(self):
  methods=json.loads((ROOT/'strategy/growth_inventory.json').read_text(encoding='utf-8'))['methods']; row=next(x for x in methods if x['id']=='tomorrow_locality_brief')
  self.assertEqual(row['status'],'DE_TESTAT'); self.assertEqual(row['editorial_risk'],'low'); self.assertEqual(row['measurability'],'high')
  self.assertIn('production merge',row['dependencies'])
 def test_apavil_closes_water_gap_only_in_candidate_mode(self):
  matrix=json.loads((ROOT/'strategy/source_coverage_matrix.json').read_text(encoding='utf-8'))
  self.assertEqual(matrix['coverage_profiles']['county_default']['water_sewer'],'STRUCTURED_CANDIDATE')
  self.assertTrue(any(x['source_id']=='apavil_valcea_outages' and x['status']=='structured_candidate' for x in matrix['source_scope']))
 def test_distributie_closes_electricity_gap_only_in_candidate_mode(self):
  matrix=json.loads((ROOT/'strategy/source_coverage_matrix.json').read_text(encoding='utf-8'))
  self.assertEqual(matrix['coverage_profiles']['county_default']['electricity'],'STRUCTURED_CANDIDATE')
  self.assertTrue(any(x['source_id']=='distributie_oltenia_valcea_planned' and x['status']=='structured_candidate' for x in matrix['source_scope']))

if __name__=='__main__': unittest.main()
