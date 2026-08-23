from pathlib import Path
import base64,hashlib,json
ROOT=Path(__file__).resolve().parents[1]; SRC=ROOT/'media_source'
def materialize_media(target:Path):
    target.mkdir(parents=True,exist_ok=True); m=json.loads((SRC/'manifest.json').read_text()); n=0
    for name,spec in m.items():
        b=base64.b64decode((SRC/(name+'.b64')).read_text().strip())
        if len(b)!=spec['size'] or hashlib.sha256(b).hexdigest()!=spec['sha256']: raise ValueError('media hash mismatch: '+name)
        (target/name).write_bytes(b); n+=1
    return n
def read_media(name):
    m=json.loads((SRC/'manifest.json').read_text()); spec=m[name]; b=base64.b64decode((SRC/(name+'.b64')).read_text().strip())
    if hashlib.sha256(b).hexdigest()!=spec['sha256']: raise ValueError('media hash mismatch: '+name)
    return b
