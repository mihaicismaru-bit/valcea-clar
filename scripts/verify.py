#!/usr/bin/env python3
from pathlib import Path
from html.parser import HTMLParser
import re,sys,os,json
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'_site'; errors=[]
BASE=os.getenv('VALCEA_CLAR_BASE_PATH','').rstrip('/')
PREVIEW=os.getenv('VALCEA_CLAR_PREVIEW','')=='1'
forbidden=['ChatGPT Sites','live-bridge.js','route-bridge.js','live-feed.json','sites.google.com']
article_updates={}
articles_path=ROOT/'content'/'articles.json'
if articles_path.is_file():
 doc=json.loads(articles_path.read_text(encoding='utf-8'))
 for row in doc.get('articles',[]):
  if not isinstance(row,dict) or not row.get('id'): continue
  updated=row.get('updated') or row.get('updated_at') or row.get('modified')
  if updated and str(updated)!=str(row.get('published') or ''):
   article_updates[str(row['id'])]=str(updated)
def local_ref(s):
 if BASE and s==BASE: return '/'
 if BASE and s.startswith(BASE+'/'): return s[len(BASE):]
 return s
class P(HTMLParser):
 def __init__(self,p):super().__init__();self.p=p
 def handle_starttag(self,t,a):
  d=dict(a)
  if t=='img':
   s=d.get('src','')
   if re.match(r'https?://',s):errors.append(f'{self.p}: remote image')
   if s.startswith('/'):
    q=local_ref(s)
    if not (OUT/q.lstrip('/')).exists():errors.append(f'{self.p}: missing {s}')
for f in OUT.rglob('*.html'):
 t=f.read_text(encoding='utf-8'); P(f).feed(t)
 for x in forbidden:
  if x in t:errors.append(f'{f}: forbidden {x}')
 for href in re.findall(r'href="(/[^"#?]*)',t):
  q=local_ref(href)
  target=OUT/'index.html' if q=='/' else (OUT/q.strip('/')/'index.html')
  if '.' in Path(q).name: target=OUT/q.lstrip('/')
  if not target.exists():errors.append(f'{f}: broken {href}')
 rel=f.relative_to(OUT).as_posix()
 if not PREVIEW and rel=='index.html' and 'max-image-preview:large' not in t:
  errors.append(f'{f}: missing max-image-preview:large')
 if rel.startswith('stiri/') and rel!='stiri/index.html':
  for marker in ['"@type":"NewsArticle"','property="og:type" content="article"','name="twitter:card"']:
   if marker not in t:errors.append(f'{f}: missing metadata {marker}')
  if not PREVIEW and 'max-image-preview:large' not in t:
   errors.append(f'{f}: missing max-image-preview:large')
  story_id=rel.split('/')[1] if len(rel.split('/'))>1 else ''
  expected_updated=article_updates.get(story_id)
  if expected_updated:
   if 'Actualizat ' not in t:
    errors.append(f'{f}: missing visible material-update timestamp')
   if f'"dateModified":"{expected_updated}"' not in t:
    errors.append(f'{f}: dateModified does not match canonical updated timestamp')
if errors:print('VERIFY FAIL\n- '+'\n- '.join(errors));sys.exit(1)
print(f'VERIFY PASS: public routes/media intact; Sites bridge absent; NewsArticle/social/discovery metadata present; base={BASE or "/"}; preview={PREVIEW}.')
