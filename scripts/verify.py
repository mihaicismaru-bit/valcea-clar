#!/usr/bin/env python3
from pathlib import Path
from html.parser import HTMLParser
import re,sys
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'_site'; errors=[]
forbidden=['ChatGPT Sites','live-bridge.js','route-bridge.js','live-feed.json','sites.google.com','/unde-iesim/','Unde ieșim']
class P(HTMLParser):
 def __init__(self,p):super().__init__();self.p=p
 def handle_starttag(self,t,a):
  d=dict(a)
  if t=='img':
   s=d.get('src','')
   if re.match(r'https?://',s):errors.append(f'{self.p}: remote image')
   if s.startswith('/') and not (OUT/s.lstrip('/')).exists():errors.append(f'{self.p}: missing {s}')
for f in OUT.rglob('*.html'):
 t=f.read_text(encoding='utf-8'); P(f).feed(t)
 for x in forbidden:
  if x in t:errors.append(f'{f}: forbidden {x}')
 for href in re.findall(r'href="(/[^"#?]*)',t):
  target=OUT/'index.html' if href=='/' else (OUT/href.strip('/')/'index.html')
  if '.' in Path(href).name: target=OUT/href.lstrip('/')
  if not target.exists():errors.append(f'{f}: broken {href}')
if errors:print('VERIFY FAIL\n- '+'\n- '.join(errors));sys.exit(1)
print('VERIFY PASS: no remote images, no Sites bridge, no missing local media, no broken internal routes.')
