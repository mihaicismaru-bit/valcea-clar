#!/usr/bin/env python3
from __future__ import annotations
import argparse, html, json, re, sys, urllib.request, urllib.parse
from html.parser import HTMLParser
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; NR=ROOT/'newsroom'; OUT=NR/'output'; STATE=NR/'state'
def load(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def dump(p,x): Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def clean(s): return re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]+>',' ',s or ''))).strip()
def fetch(url,timeout=18):
 req=urllib.request.Request(url,headers={'User-Agent':'ValceaClarNewsroom/1.0 (+https://valceaclar.ro)'})
 with urllib.request.urlopen(req,timeout=timeout) as r:return r.read().decode(r.headers.get_content_charset() or 'utf-8','replace')
class Links(HTMLParser):
 def __init__(self):super().__init__();self.rows=[];self.a=None;self.buf=[]
 def handle_starttag(self,t,a):
  if t=='a':self.a=dict(a).get('href');self.buf=[]
 def handle_data(self,d):
  if self.a is not None:self.buf.append(d)
 def handle_endtag(self,t):
  if t=='a' and self.a is not None:self.rows.append((clean(''.join(self.buf)),self.a));self.a=None
def items(src,text):
 base=src['url'];out=[]
 if src['adapter'] in {'rss','atom'}:
  for block in re.findall(r'<(?:item|entry)\b.*?</(?:item|entry)>',text,re.I|re.S):
   mt=re.search(r'<title[^>]*>(.*?)</title>',block,re.I|re.S);title=clean(mt.group(1)) if mt else ''
   m=re.search(r'<link[^>]+href=["\']([^"\']+)',block,re.I) or re.search(r'<link[^>]*>(.*?)</link>',block,re.I|re.S)
   url=clean(m.group(1)) if m else ''
   if title and url:out.append((title,urllib.parse.urljoin(base,url)))
 else:
  p=Links();p.feed(text)
  for title,url in p.rows:
   u=urllib.parse.urljoin(base,url);path=urllib.parse.urlparse(u).path.lower();inc=src.get('include_path_contains') or []
   if len(title)<src.get('min_title_length',12):continue
   if inc and not any(x.lower() in path for x in inc):continue
   if src.get('same_host_only') and urllib.parse.urlparse(u).netloc!=urllib.parse.urlparse(base).netloc:continue
   out.append((title,u))
 seen=set();rows=[]
 for t,u in out:
  u=u.split('#')[0]
  if u not in seen:rows.append((t,u));seen.add(u)
 return rows[:40]
def risk(text,pol):return sorted({x for x in pol['risk_terms'] if x in text.lower()})
def score(src,title,pol):
 s=38 if src['tier']=='T1' else 24;s+=12 if src.get('local_by_definition') else 0;s+=18 if src.get('material_by_definition') else 0;s+=min(24,6*sum(x in title.lower() for x in pol['material_terms']));return min(100,s)
def decision(src,sc,risks,pol):
 if risks:return 'REVIEW_REQUIRED'
 th=pol['ready_score_t1'] if src['tier']=='T1' else pol['ready_score_t2'];return 'READY' if sc>=th else 'WATCH'
def product(c,h,d,p,section):
 ident=re.sub(r'[^a-z0-9]+','-',c['source_id']+'-'+str(abs(hash(c['url'])))).strip('-')[:80]
 return {'id':ident,'section':section,'headline':h,'dek':d,'paragraphs':p,'sources':[{'name':c['source_name'],'url':c['url'],'tier':c['tier']}],'source_candidate':c,'status':'DRAFT_CANDIDATE_ONLY','image':None}
def cj_story(c,detail):
 txt=clean(detail);money=[]
 for m in re.finditer(r'(\d{1,3}(?:[.\s]\d{3})+)\s*(?:mii\s*)?lei',txt,re.I):
  raw=m.group(1).replace(' ','').replace('.','');v=int(raw)
  if 'mii' in m.group(0).lower():v*=1000
  money.append(v)
 amt=max(money) if money else None;head='CJ Vâlcea: proiectele de pe ordinea de zi a următoarei ședințe'
 if amt:head=f'CJ Vâlcea: pe ordinea de zi, proiecte care includ {amt:,} lei'.replace(',','.')
 p=['Consiliul Județean Vâlcea a publicat ordinea de zi a unei ședințe. VÂLCEA CLAR tratează documentul ca proiect de lucru, nu ca hotărâri deja adoptate.']
 if amt:p.append(f'Cea mai mare sumă identificată automat în document este {amt:,} lei. Valoarea trebuie citită în contextul proiectului și al anexelor sale.'.replace(',','.'))
 p.append('Adoptarea, modificarea sau respingerea proiectelor se confirmă numai după ședință, din hotărârile și documentele oficiale publicate ulterior.')
 return product(c,head,'Ce intră în discuția consilierilor județeni și ce nu poate fi prezentat încă drept decizie.',p,'ADMINISTRAȚIE')
def isu_story(c,detail,pol):
 txt=clean(detail);rr=risk(txt,pol)
 if rr:return None,'REVIEW_REQUIRED_DETAIL:'+','.join(rr)
 def n(p):
  m=re.search(p,txt,re.I);return int(m.group(1)) if m else None
 missions=n(r'(\d+)\s+(?:de\s+)?misiuni');medical=n(r'(\d+)\s+(?:de\s+)?intervenții[^.]{0,60}(?:medical|SMURD)');fires=n(r'(\d+)\s+incend')
 nums=[x for x in [missions,medical,fires] if x is not None]
 if not nums:return None,'ISU_STRUCTURE_NOT_RESOLVED'
 parts=[]
 if missions is not None:parts.append(f'{missions} misiuni')
 if medical is not None:parts.append(f'{medical} intervenții medicale')
 if fires is not None:parts.append(f'{fires} incendii')
 return product(c,'ISU Vâlcea: '+', '.join(parts),'Bilanț operativ extras din comunicatul oficial ISU Vâlcea.',[f'ISU Vâlcea raportează {", ".join(parts)} în intervalul prezentat de instituție.','Cifrele sunt preluate din comunicatul oficial; incidentele individuale cu victime nu sunt automat transformate în articole fără review editorial.'],'ACTUALITATE'),None
def choose_media(s):return 'administratie-ramnicu-valcea-20260819.webp' if s['section']=='ADMINISTRAȚIE' else None
def fixture_rows():
 return [
 {'source_id':'cj_valcea_sedinte_publice','source_name':'Consiliul Județean Vâlcea — ședințe publice','tier':'T1','url':'https://cjvalcea.ro/avn_sedinte_cj/26-08-2026/','title':'Ședința Consiliului Județean Vâlcea din 26 august 2026','score':88,'decision':'READY','risks':[],'detail':'repartizarea sumei de 43.793 mii lei pentru UAT-uri; proiecte privind execuția bugetară, transportul elevilor și spitale'},
 {'source_id':'isu_valcea_comunicate','source_name':'ISU Vâlcea','tier':'T1','url':'https://isuvl.igsu.ro/stiri-locale/misiunile-pompierilor-1','title':'Misiunile pompierilor în ultimele 48 de ore','score':70,'decision':'READY','risks':[],'detail':'54 misiuni. 41 intervenții medicale SMURD. 7 incendii.'},
 {'source_id':'isu_valcea_comunicate','source_name':'ISU Vâlcea','tier':'T1','url':'https://isuvl.igsu.ro/stiri-locale/misiunile-pompierilor-2','title':'Misiunile pompierilor în ultimele 72 de ore','score':70,'decision':'READY','risks':[],'detail':'60 misiuni. 44 intervenții medicale. un bărbat decedat. 5 incendii.'}]
def cycle(fixtures=False):
 cfg=load(NR/'sources.json');pol=load(NR/'policy.json');seen=set(load(STATE/'seen.json').get('urls',[]));candidates=[];health=[]
 if fixtures:candidates=fixture_rows()
 else:
  for src in cfg['sources']:
   if not src.get('enabled'):continue
   try:
    text=fetch(src['url']);rows=items(src,text);health.append({'id':src['id'],'ok':True,'items':len(rows)})
    for title,url in rows:
     sc=score(src,title,pol);rr=risk(title,pol);candidates.append({'source_id':src['id'],'source_name':src['name'],'tier':src['tier'],'url':url,'title':title,'score':sc,'decision':decision(src,sc,rr,pol),'risks':rr,'seen_before':url in seen})
   except Exception as e:health.append({'id':src['id'],'ok':False,'error':str(e)[:180]})
 candidates=sorted(candidates,key=lambda x:(x['decision']=='READY',x['score']),reverse=True)[:120];stories=[];holds=[]
 for c in candidates:
  if c['decision']!='READY':continue
  src=next((s for s in cfg['sources'] if s['id']==c['source_id']),{});adapter=src.get('structured_detail_adapter')
  if not adapter:continue
  try:detail=c.get('detail') or fetch(c['url'])
  except Exception as e:holds.append({'url':c['url'],'reason':'DETAIL_FETCH:'+str(e)[:120]});continue
  if adapter=='cj_agenda':s=cj_story(c,detail);hold=None
  elif adapter=='isu_release':s,hold=isu_story(c,detail,pol)
  else:s=None;hold='NO_ADAPTER'
  if hold:holds.append({'url':c['url'],'reason':hold});continue
  if s:s['image']=choose_media(s);stories.append(s)
 queue=[{'id':s['id'],'headline':s['headline'],'status':'LOCKED_CANDIDATE_ONLY'} for s in stories]
 dump(OUT/'candidates.json',{'status':'candidate_only','candidates':candidates,'source_health':health});dump(OUT/'stories.json',{'status':'candidate_only','stories':stories,'holds':holds});dump(OUT/'queue.json',{'status':'LOCKED_CANDIDATE_ONLY','queue':queue})
 if not fixtures:dump(STATE/'seen.json',{'urls':sorted(seen|{x['url'] for x in candidates})[-2500:]})
 review(stories,holds);return candidates,stories,holds
def review(stories=None,holds=None):
 if stories is None:
  d=load(OUT/'stories.json');stories=d.get('stories',[]);holds=d.get('holds',[])
 cards=[]
 for s in stories:cards.append(f'<article><b>DRAFT</b><h2>{html.escape(s["headline"])}</h2><p>{html.escape(s["dek"])}</p><small>{html.escape(s["sources"][0]["url"])}</small><p>Media: {html.escape(str(s.get("image") or "fără imagine"))}</p></article>')
 for x in holds:cards.append(f'<article class="hold"><b>HOLD</b><p>{html.escape(x["reason"])}</p><small>{html.escape(x["url"])}</small></article>')
 (OUT/'review.html').write_text('<!doctype html><meta charset="utf-8"><title>VÂLCEA CLAR Newsroom Review</title><style>body{font:16px Arial;max-width:1000px;margin:40px auto;padding:0 20px}article{border-top:2px solid #111;padding:18px 0}.hold{background:#fff2f2}</style><h1>Newsroom Review — candidate only</h1>'+''.join(cards),encoding='utf-8')
def verify():
 pol=load(NR/'policy.json');q=load(OUT/'queue.json');s=load(OUT/'stories.json');errs=[]
 if pol.get('publication_mode')!='candidate_only' or pol.get('auto_publish') is not False:errs.append('publication authority unlocked')
 if q.get('status')!='LOCKED_CANDIDATE_ONLY':errs.append('queue unlocked')
 for x in s.get('stories',[]):
  if not x.get('sources') or any(not y.get('url') for y in x['sources']):errs.append('story without source')
  if x.get('image') and x['section']!='ADMINISTRAȚIE':errs.append('unsafe contextual media assignment')
 if errs:print('NEWSROOM VERIFY FAIL\n- '+'\n- '.join(errs));return 1
 print(f'NEWSROOM VERIFY PASS: {len(load(NR/"sources.json")["sources"])} sources; candidate_only; {len(s.get("stories",[]))} structured drafts.');return 0
def main():
 ap=argparse.ArgumentParser();ap.add_argument('cmd',choices=['cycle','verify','review','publish']);ap.add_argument('--fixtures',action='store_true');a=ap.parse_args()
 if a.cmd=='cycle':cycle(a.fixtures)
 elif a.cmd=='verify':raise SystemExit(verify())
 elif a.cmd=='review':review()
 else:print('NEWSROOM PUBLISH BLOCKED: publication_mode is not live');raise SystemExit(2)
if __name__=='__main__':main()
