import subprocess,sys,unittest
from datetime import timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'scripts'))
import newsroom
class T(unittest.TestCase):
 def test_sources(self): self.assertEqual(len(newsroom.load(ROOT/'newsroom/sources.json')['sources']),11)
 def test_policy_locked(self):
  p=newsroom.load(ROOT/'newsroom/policy.json'); self.assertEqual(p['publication_mode'],'candidate_only'); self.assertFalse(p['auto_publish'])
 def test_risk(self):
  p=newsroom.load(ROOT/'newsroom/policy.json'); self.assertTrue(any(x.startswith('deced') for x in newsroom.risk('un bărbat decedat',p))); self.assertTrue(newsroom.risk('persoană cercetată pentru trafic de minori',p))
 def test_safe_negation(self):
  p=newsroom.load(ROOT/'newsroom/policy.json'); self.assertFalse(newsroom.risk('intervenție fără victime și fără persoane rănite',p))
 def test_same_title_different_url(self):
  r=newsroom.fixture_rows(); self.assertNotEqual(r[1]['url'],r[2]['url']); self.assertTrue(r[1]['title'].startswith('Misiunile')); self.assertTrue(r[2]['title'].startswith('Misiunile'))
 def test_fixture_cycle(self):
  c,s,h=newsroom.cycle(True); self.assertEqual((len(c),len(s),len(h)),(3,2,1))
 def test_cj_money(self):
  _,s,_=newsroom.cycle(True); self.assertIn('43.793.000',s[0]['headline'])
 def test_isu(self):
  _,s,_=newsroom.cycle(True); self.assertTrue(any('54 misiuni' in x['headline'] for x in s))
 def test_tragic_hold(self):
  _,_,h=newsroom.cycle(True); self.assertTrue(any('REVIEW_REQUIRED_DETAIL' in x['reason'] for x in h))
 def test_freshness_gate(self):
  old=newsroom.datetime.now(newsroom.ZoneInfo('Europe/Bucharest')).date()-timedelta(days=5); c={'url':f'https://example.test/{old.day:02d}-{old.month:02d}-{old.year}/'}; self.assertTrue(newsroom.freshness_hold({'max_age_days':4},c,'').startswith('STALE_DETAIL'))
 def test_media(self):
  _,s,_=newsroom.cycle(True); cj=[x for x in s if x['section']=='ADMINISTRAȚIE'][0]; isu=[x for x in s if x['section']=='ACTUALITATE'][0]; self.assertTrue(cj['image']); self.assertIsNone(isu['image'])
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
 def test_verify_and_publish_lock(self):
  newsroom.cycle(True); self.assertEqual(newsroom.verify(),0); p=subprocess.run([sys.executable,str(ROOT/'scripts/newsroom.py'),'publish']); self.assertNotEqual(p.returncode,0)
if __name__=='__main__':unittest.main()
