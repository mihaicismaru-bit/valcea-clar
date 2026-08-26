import subprocess,sys,unittest
from collections import Counter
from datetime import timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'scripts'))
import newsroom
class T(unittest.TestCase):
 def test_sources(self): self.assertEqual(len(newsroom.load(ROOT/'newsroom/sources.json')['sources']),13)
 def test_policy_locked(self):
  p=newsroom.load(ROOT/'newsroom/policy.json'); self.assertEqual(p['publication_mode'],'candidate_only'); self.assertFalse(p['auto_publish'])
 def test_risk(self):
  p=newsroom.load(ROOT/'newsroom/policy.json'); self.assertTrue(any(x.startswith('deced') for x in newsroom.risk('un bărbat decedat',p))); self.assertTrue(newsroom.risk('persoană cercetată pentru trafic de minori',p))
 def test_safe_negation(self):
  p=newsroom.load(ROOT/'newsroom/policy.json'); self.assertFalse(newsroom.risk('intervenție fără victime și fără persoane rănite',p))
 def test_same_title_different_url(self):
  r=newsroom.fixture_rows(); self.assertNotEqual(r[1]['url'],r[2]['url']); self.assertTrue(r[1]['title'].startswith('Misiunile')); self.assertTrue(r[2]['title'].startswith('Misiunile'))
 def test_fixture_cycle(self):
  c,s,h=newsroom.cycle(True,persist=False); self.assertEqual((len(c),len(s),len(h)),(3,2,1))
 def test_fixture_cycle_does_not_overwrite_live_outputs(self):
  paths=[ROOT/'newsroom/output/candidates.json',ROOT/'newsroom/output/stories.json',ROOT/'newsroom/output/queue.json',ROOT/'newsroom/output/locality_brief.json',ROOT/'newsroom/output/review.html']
  before={path:path.read_bytes() for path in paths}; newsroom.cycle(True,persist=False); after={path:path.read_bytes() for path in paths}; self.assertEqual(before,after)
 def test_cj_money(self):
  _,s,_=newsroom.cycle(True,persist=False); self.assertIn('43.793.000',s[0]['headline'])
 def test_isu(self):
  _,s,_=newsroom.cycle(True,persist=False); self.assertTrue(any('54 misiuni' in x['headline'] for x in s))
 def test_tragic_hold(self):
  _,_,h=newsroom.cycle(True,persist=False); self.assertTrue(any('REVIEW_REQUIRED_DETAIL' in x['reason'] for x in h))
 def test_freshness_gate(self):
  old=newsroom.datetime.now(newsroom.ZoneInfo('Europe/Bucharest')).date()-timedelta(days=5); c={'url':f'https://example.test/{old.day:02d}-{old.month:02d}-{old.year}/'}; self.assertTrue(newsroom.freshness_hold({'max_age_days':4},c,'').startswith('STALE_DETAIL'))
 def test_media(self):
  _,s,_=newsroom.cycle(True,persist=False); cj=[x for x in s if x['section']=='ADMINISTRAȚIE'][0]; isu=[x for x in s if x['section']=='ACTUALITATE'][0]; self.assertTrue(cj['image']); self.assertIsNone(isu['image'])
 def test_inhga_92_extracts_and_matches_valcea(self):
  detail=(ROOT/'tests/fixtures/inhga_warning_92.html').read_text(encoding='utf-8'); facts=newsroom.parse_inhga_warning(detail)
  self.assertEqual(facts['number'],92); self.assertEqual(facts['issue_date'],'2026-08-25'); self.assertEqual(facts['levels'],['GALBEN']); self.assertIn('Vâlcea',facts['counties']); self.assertTrue(facts['valcea_relevant']); self.assertTrue(facts['valcea_segments']); self.assertEqual(facts['valid_until'],'2026-08-27T00:00:00+03:00')
  candidate={'source_id':'inhga_hydrological_warnings','source_name':'INHGA','tier':'T1','url':'https://www.hidro.ro/warning/atentionare-hidrologica-nr-92-din-25-08-2026/','title':'ATENŢIONARE HIDROLOGICĂ NR. 92 DIN 25.08.2026','score':68,'decision':'READY','risks':[]}
  story,hold=newsroom.inhga_story(candidate,detail,newsroom.datetime(2026,8,25,20,0,tzinfo=newsroom.ZoneInfo('Europe/Bucharest'))); self.assertIsNone(hold); self.assertEqual(story['structured_facts']['number'],92)
 def test_inhga_non_valcea_fails_closed(self):
  detail=(ROOT/'tests/fixtures/inhga_warning_non_valcea.html').read_text(encoding='utf-8'); facts=newsroom.parse_inhga_warning(detail); self.assertFalse(facts['valcea_relevant'])
  candidate={'source_id':'inhga_hydrological_warnings','source_name':'INHGA','tier':'T1','url':'https://www.hidro.ro/warning/test/','title':'ATENŢIONARE HIDROLOGICĂ NR. 93 DIN 25.08.2026','score':68,'decision':'READY','risks':[]}
  story,hold=newsroom.inhga_story(candidate,detail,newsroom.datetime(2026,8,25,20,0,tzinfo=newsroom.ZoneInfo('Europe/Bucharest'))); self.assertIsNone(story); self.assertEqual(hold,'INHGA_NOT_VALCEA')
 def test_inhga_is_not_live_authorized(self):
  pub=newsroom.load(ROOT/'newsroom/publication.json'); self.assertNotIn('inhga_hydrological_warnings',pub['allowed_source_ids'])
 def test_distributie_oltenia_index_is_bounded_and_not_live_authorized(self):
  cfg=newsroom.load(ROOT/'newsroom/sources.json'); src=next(x for x in cfg['sources'] if x['id']=='distributie_oltenia_valcea_planned')
  detail=(ROOT/'tests/fixtures/distributie_oltenia_valcea_index.html').read_text(encoding='utf-8'); rows=newsroom.items(src,detail)
  self.assertEqual(len(rows),2); self.assertIn('31.08 - 06.09.2026',rows[0][0]); self.assertIn('24.08 - 30.08.2026',rows[1][0])
  pub=newsroom.load(ROOT/'newsroom/publication.json'); self.assertNotIn(src['id'],pub['allowed_source_ids'])
 def test_distributie_schedule_rows_deduplicate_expire_and_stay_candidate(self):
  detail=(ROOT/'tests/fixtures/distributie_oltenia_schedule.txt').read_text(encoding='utf-8'); facts=newsroom.parse_distributie_schedule(detail,'https://example.test/week.pdf')
  self.assertEqual(facts['total_time_rows'],10); self.assertEqual(facts['parsed_rows'],10); self.assertEqual(len({x['id'] for x in facts['rows']}),10)
  candidate={'source_id':'distributie_oltenia_valcea_planned','source_name':'Distribuție Oltenia','tier':'T1','url':'https://example.test/week.pdf','title':'Valcea - Intreruperi 24.08 - 30.08.2026','score':68,'decision':'READY','risks':[]}
  story,hold=newsroom.distributie_story(candidate,detail,newsroom.datetime(2026,8,25,23,30,tzinfo=newsroom.ZoneInfo('Europe/Bucharest')))
  self.assertIsNone(hold); self.assertEqual(len(story['structured_facts']['active_rows']),6); self.assertIn('6 localități',story['headline'])
  story,hold=newsroom.distributie_story(candidate,detail,newsroom.datetime(2026,8,31,0,0,tzinfo=newsroom.ZoneInfo('Europe/Bucharest'))); self.assertIsNone(story); self.assertEqual(hold,'DISTRIBUTIE_NO_ACTIVE_ROWS')
 def test_distributie_partial_table_fails_closed(self):
  detail='SĂPTĂMÂNA 31.08 - 06.09.2026 - VÂLCEA\n 31.08\n 09:00 - 17:00  Drăgășani  Zona A\n 09:00 - 17:00\n 09:00 - 17:00\n'
  candidate={'source_id':'distributie_oltenia_valcea_planned','source_name':'Distribuție Oltenia','tier':'T1','url':'https://example.test/week.pdf','title':'test','score':68,'decision':'READY','risks':[]}
  story,hold=newsroom.distributie_story(candidate,detail,newsroom.datetime(2026,8,25,23,30,tzinfo=newsroom.ZoneInfo('Europe/Bucharest'))); self.assertIsNone(story); self.assertEqual(hold,'DISTRIBUTIE_PARTIAL_TABLE:1/3')
 def test_distributie_raw_multiline_table_is_complete_and_date_safe(self):
  detail=(ROOT/'tests/fixtures/distributie_oltenia_multiline_raw.txt').read_text(encoding='utf-8'); facts=newsroom.parse_distributie_schedule(detail,'https://example.test/next-week.pdf')
  self.assertEqual((facts['parsed_rows'],facts['total_time_rows'],facts['unresolved_rows']),(27,27,[]))
  by_day=Counter(x['valid_from'][:10] for x in facts['rows']); self.assertEqual(by_day,{'2026-08-31':5,'2026-09-01':7,'2026-09-02':3,'2026-09-03':6,'2026-09-04':6})
  self.assertEqual(sum(x['interruption_kind']=='short_duration_pair' for x in facts['rows']),7)
  self.assertTrue(any(x['uat']=='Nicolae Bălcescu' for x in facts['rows'])); self.assertTrue(any(x['uat']=='Zătreni' for x in facts['rows']))
 def test_tomorrow_locality_brief_is_candidate_only_and_localized(self):
  detail=(ROOT/'tests/fixtures/distributie_oltenia_schedule.txt').read_text(encoding='utf-8'); candidate={'source_id':'distributie_oltenia_valcea_planned','source_name':'Distribuție Oltenia','tier':'T1','url':'https://example.test/week.pdf','title':'test','score':68,'decision':'READY','risks':[]}
  now=newsroom.datetime(2026,8,26,0,5,tzinfo=newsroom.ZoneInfo('Europe/Bucharest')); story,hold=newsroom.distributie_story(candidate,detail,now); self.assertIsNone(hold)
  brief=newsroom.tomorrow_locality_brief([story],now); self.assertEqual(brief['status'],'candidate_only'); self.assertEqual(brief['target_date'],'2026-08-27'); self.assertEqual(brief['total_localities'],2); self.assertEqual({x['uat'] for x in brief['localities']},{'Călimănești','Stroești'})
 def test_apavil_index_and_structured_expiry_gate(self):
  cfg=newsroom.load(ROOT/'newsroom/sources.json'); src=next(x for x in cfg['sources'] if x['id']=='apavil_valcea_outages')
  index=(ROOT/'tests/fixtures/apavil_outages_index.html').read_text(encoding='utf-8'); rows=newsroom.items(src,index)
  self.assertEqual(len(rows),2); self.assertTrue(all('/materiale/anunturi/' in url for _,url in rows))
  detail=(ROOT/'tests/fixtures/apavil_outage_future.html').read_text(encoding='utf-8'); facts=newsroom.parse_apavil_outage(detail)
  self.assertEqual(facts['outage_date'],'2026-08-26'); self.assertEqual(facts['uats'],['Râmnicu Vâlcea','Mihăești'])
  candidate={'source_id':src['id'],'source_name':src['name'],'tier':'T1','url':rows[0][1],'title':rows[0][0],'score':68,'decision':'READY','risks':[]}
  story,hold=newsroom.apavil_story(candidate,detail,newsroom.datetime(2026,8,25,22,0,tzinfo=newsroom.ZoneInfo('Europe/Bucharest'))); self.assertIsNone(hold); self.assertEqual(story['section'],'UTILITĂȚI')
  story,hold=newsroom.apavil_story(candidate,detail,newsroom.datetime(2026,8,26,16,0,tzinfo=newsroom.ZoneInfo('Europe/Bucharest'))); self.assertIsNone(story); self.assertTrue(hold.startswith('APAVIL_EXPIRED'))
  pub=newsroom.load(ROOT/'newsroom/publication.json'); self.assertNotIn(src['id'],pub['allowed_source_ids'])
 def test_verify_and_publish_lock(self):
  self.assertEqual(newsroom.verify(),0); p=subprocess.run([sys.executable,str(ROOT/'scripts/newsroom.py'),'publish']); self.assertNotEqual(p.returncode,0)
if __name__=='__main__':unittest.main()
