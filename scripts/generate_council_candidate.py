"""Generate a strictly attributed agenda-based brief from a collected HTML record."""
import argparse
from datetime import date, datetime
import json
import re
import sqlite3
from pathlib import Path
try:
    from scripts.publish_from_evidence import under
except ModuleNotFoundError:
    from publish_from_evidence import under

MONTHS = ('ianuarie','februarie','martie','aprilie','mai','iunie','iulie','august','septembrie','octombrie','noiembrie','decembrie')

def candidate(snapshot, url, sha, meeting):
    db=sqlite3.connect((snapshot/'evidence.sqlite').resolve().as_uri()+'?mode=ro&immutable=1',uri=True)
    try:
        row=db.execute('select text_path from versions where url=? and sha=?',(url,sha)).fetchone()
    finally:
        db.close()
    if not row: raise ValueError('collected document is missing')
    text=under(snapshot.resolve(),row[0]).read_text(encoding='utf-8')
    day=f'{meeting.day} {MONTHS[meeting.month-1]} {meeting.year}'
    if day not in text.casefold(): raise ValueError('meeting date missing')
    if not 0 <= (date.today()-meeting).days <= 7:
        raise ValueError('meeting is too old for this current-news template')
    entries=[x.split(' Descarcă ')[0].strip() for x in text.splitlines()
             if '. Proiect de hotărâre:' in x and x.split('.')[0].isdigit()]
    gambling=[x for x in entries if 'jocuri de noroc' in x.casefold()]
    betting=[x for x in gambling if 'pariuri' in x.casefold()]
    slots=[x for x in gambling if 'slot machine' in x.casefold()]
    if len(gambling)<2 or len(gambling)!=len(betting)+len(slots):
        raise ValueError('unsupported gambling proposal mix')
    evidence='Proiect de hotărâre: Acordare autorizație de funcționare jocuri de noroc'
    short_day=f'{meeting.day} {MONTHS[meeting.month-1]}'
    return {'id':f'ramnicu-consiliu-proiecte-jocuri-noroc-{meeting.day}-{MONTHS[meeting.month-1]}-{meeting.year}',
            'source_url':url,'source_sha256':sha,'editorially_verified':False,
            'section':'ADMINISTRAȚIE','headline':f'Râmnicu Vâlcea: {len(gambling)} proiecte pentru jocuri de noroc pe agenda ședinței din {short_day}',
            'dek':f'Lista publicată de Primărie pentru ședința din {short_day} include {len(betting)} proiecte pentru pariuri și {len(slots)} pentru slot machine.',
            'published':datetime.now().astimezone().isoformat(timespec='seconds'),
            'paragraphs':[
                {'text':f'Consiliul Local Râmnicu Vâlcea a avut pe ordinea de zi a ședinței convocate pentru {short_day} {len(gambling)} proiecte privind autorizarea unor puncte de jocuri de noroc, potrivit listei publicate de Primărie. Dintre acestea, {len(betting)} se refereau la pariuri în cotă fixă și {len(slots)} la slot machine.', 'source_excerpt':evidence},
                {'text':'Documentul Primăriei este o convocare cu proiecte de hotărâre. El nu consemnează rezultatul voturilor și nu arată care dintre autorizații au fost acordate; aceste informații trebuie urmărite în hotărârile și procesul-verbal al ședinței.', 'source_excerpt':'Proiect de hotărâre: Acordare autorizație anuală de funcționare jocuri de noroc slot machine'}]}

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--snapshot',type=Path,required=True)
    p.add_argument('--source-url',required=True)
    p.add_argument('--source-sha',required=True)
    p.add_argument('--meeting',type=date.fromisoformat,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    a.output.write_text(json.dumps(candidate(a.snapshot,a.source_url,a.source_sha,a.meeting),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('candidate prepared; editorial review required before projection')
