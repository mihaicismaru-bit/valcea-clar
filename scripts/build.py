#!/usr/bin/env python3
from pathlib import Path
import json,html,shutil
from media_assets import materialize_media
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'_site'; C=ROOT/'content'
def load(n): return json.loads((C/n).read_text(encoding='utf-8'))
def h(s): return html.escape(str(s),quote=True)
arts=load('articles.json')['articles']; legal=load('legal.json'); css=(C/'site.css').read_text()
if OUT.exists():shutil.rmtree(OUT)
OUT.mkdir(); (OUT/'assets').mkdir(); (OUT/'assets/site.css').write_text(css,encoding='utf-8'); materialize_media(OUT/'media')
nav='<nav><a href="/">Acasă</a><a href="/stiri/">Știri</a><a href="/despre/">Despre</a></nav>'
def shell(title,body,desc='Știri locale verificate din Vâlcea.'):
 return f'''<!doctype html><html lang="ro"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{h(title)}</title><meta name="description" content="{h(desc)}"><link rel="canonical" href="https://valceaclar.ro/"><link rel="stylesheet" href="/assets/site.css"></head><body><header><a class="brand" href="/">VÂLCEA CLAR</a>{nav}</header><main>{body}</main><footer>VÂLCEA CLAR · redactie@valceaclar.ro · <a href="/termeni/">Termeni</a> · <a href="/confidentialitate/">Confidențialitate</a></footer></body></html>'''
def img(a,hero=False):
 n=a.get('image'); return '' if not n else f'<img src="/media/{h(n)}" alt="Imagine de context din arhiva VÂLCEA CLAR" loading="{"eager" if hero else "lazy"}">'
def route(path,text):
 d=OUT/path.strip('/'); d.mkdir(parents=True,exist_ok=True); (d/'index.html').write_text(text,encoding='utf-8')
arts=sorted(arts,key=lambda a:(a.get('priority',0),a.get('published','')),reverse=True)
lead=arts[0]; cards=''.join(f'<article class="card">{img(a)}<div class="kicker">{h(a["section"])}</div><h2><a href="/stiri/{h(a["id"])}/">{h(a["headline"])}</a></h2><p>{h(a["dek"])}</p></article>' for a in arts[1:])
home=f'<section class="hero">{img(lead,True)}<div class="kicker">{h(lead["section"])}</div><h1><a href="/stiri/{h(lead["id"])}/">{h(lead["headline"])}</a></h1><p>{h(lead["dek"])}</p></section><section class="grid">{cards}</section>'
(OUT/'index.html').write_text(shell('VÂLCEA CLAR — Știri din Vâlcea',home),encoding='utf-8')
rows=''.join(f'<article><div class="kicker">{h(a["section"])}</div><h2><a href="/stiri/{h(a["id"])}/">{h(a["headline"])}</a></h2><p>{h(a["dek"])}</p></article>' for a in arts)
route('stiri',shell('Știri — VÂLCEA CLAR',f'<h1>Știri</h1>{rows}'))
for a in arts:
 body=img(a,True)+f'<div class="kicker">{h(a["section"])}</div><h1>{h(a["headline"])}</h1><p class="dek">{h(a["dek"])}</p>'+''.join(f'<p>{h(p)}</p>' for p in a['paragraphs'])+'<h2>Surse</h2><ul>'+''.join(f'<li><a href="{h(s["url"])}" rel="nofollow noopener">{h(s["name"])}</a></li>' for s in a['sources'])+'</ul>'
 route('stiri/'+a['id'],shell(a['headline']+' — VÂLCEA CLAR',body,a['dek']))
route('despre',shell('Despre — VÂLCEA CLAR','<h1>Despre VÂLCEA CLAR</h1><p>Publicație locală axată pe fapte verificabile, documente și surse identificabile.</p><p>Automatizarea descoperă și pregătește materiale; afirmațiile cu risc reputațional ori informație incompletă sunt ținute la review.</p>'))
for slug in ['termeni','confidentialitate']:
 x=legal[slug]; body=f'<h1>{h(x["title"])}</h1><p>{h(x.get("dek",""))}</p>'+''.join(f'<section><h2>{h(sec[0])}</h2><p>{h(sec[1])}</p></section>' for sec in x['sections']); route(slug,shell(x['title']+' — VÂLCEA CLAR',body))
(OUT/'robots.txt').write_text('User-agent: *\nAllow: /\nSitemap: https://valceaclar.ro/sitemap.xml\n')
urls=['/','/stiri/','/despre/','/termeni/','/confidentialitate/']+[f'/stiri/{a["id"]}/' for a in arts]
(OUT/'sitemap.xml').write_text('<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join(f'<url><loc>https://valceaclar.ro{u}</loc></url>' for u in urls)+'</urlset>')
print(f'Built {len(urls)} routes; {len(list((OUT/"media").glob("*.webp")))} local images.')
