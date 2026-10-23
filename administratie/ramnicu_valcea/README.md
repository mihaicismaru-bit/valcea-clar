# Modulul Primăria Râmnicu Vâlcea

Decizie owner, 16 octombrie 2026: codul agenților și orchestratorului acestui modul locuiește în `mihaicismaru-bit/valcea-clar`. Această decizie înlocuiește pentru noul modul restricția istorică de repository exclusiv de prezentare. Execuția propusă este pe Synology, după verificarea runnerului și a stocării persistente.

## Ce funcționează în această etapă

- Colector Python 3.12 fără dependențe Python externe, limitat la domeniile oficiale configurate.
- Respectarea robots.txt, limită de dimensiune, pauză între cereri și controlul destinației redirecturilor.
- Originale adresate prin SHA-256, versiuni pe URL, text extras și legături părinte–anexă în SQLite.
- Frontieră persistentă: când bugetul unei runde se termină, următoarea continuă documentele neprocesate.
- Sarcini idempotente pentru Consiliul Local, Urbanism și triaj; un document poate interesa ambii specialiști.
- HTML/text și PDF cu `pdftotext` instalat. PDF-urile scanate și formatele neimplementate rămân explicit în așteptare.
- Raport per rulare cu erori, documente rămase, lipsuri de extracție și acoperirea încă nevalidată.

`analysis_queue.json` este o coadă de intrare. Nu reprezintă analize executate. `agents.json` definește contractele; apelurile către modele și orchestrarea analizelor sunt următoarea etapă.

## Utilizare

```bash
python -m administratie.ramnicu_valcea.collector --data-dir /data/ramnicu-valcea
python -m unittest discover -s tests -p 'test_ramnicu_collector.py' -v
```

Datele de lucru trebuie ținute într-un volum persistent extern repository-ului, de exemplu `/volume1/docker/valcea-clar/data/ramnicu-valcea`. Exemplele de cale nu certifică existența unui folder pe NAS.

Colectorul reia verificarea fiecărui URL după 24 de ore. `--force` ignoră intervalul pentru o verificare deliberată. O singură execuție poate deține blocarea OS. SQLite și fișierele trebuie să fie pe un volum local al NAS-ului, nu pe un share SMB/NFS.

Cod ieșire `2` = rundă degradată; vezi `latest_run.json`. `BOUNDED_SCAN_COMPLETE` înseamnă doar că frontiera configurată a fost parcursă. Nu certifică toate sursele, toate documentele sau o perioadă istorică. `pilot_status=INCOMPLETE_COVERAGE` rămâne până la validarea inventarului.

## Următoarele probe, în ordine

1. Verificare live a semințelor, a robots.txt, paginării, arhivei Domino și directoarelor Joomla; accesul prin motorul de căutare nu este dovadă de acces pentru colector.
2. Inventarul actual al consilierilor și conturilor publice ale instituției, primarului și tuturor consilierilor. Identitățile și accesul se verifică individual; niciun cont nu este ghicit. Pentru social este necesar un adaptor separat permis de platformă.
3. Recuperarea completă a unei ședințe și a unui caz de urbanism, inclusiv anexele. Verificare manuală față de inventarul documentelor.
4. Adaptor de model și orchestrarea analizelor, cu dovezi exacte și evaluarea calității. Nicio cheie API nu se introduce în repository.
5. Pilot retrospectiv de 90 de zile și șapte zile de monitorizare, cu măsurarea omisiunilor, versiunilor, extragerilor și costurilor.
6. Integrarea publicării: regulă explicită de proprietate pe modul/story_id, migrarea din fluxul existent și verificare publică după fiecare publicare.

## Publicarea și automatizarea

Pilotul nu are cod de publicare și refuză configurația `publication.enabled=true`. Fluxurile existente ale site-ului rămân active până la migrarea controlată a modulului. Agentul nou nu are acces la credențiale GitHub/social și nu poate trimite mesaje.

Nu există încă un serviciu sau un program zilnic instalat pe NAS. După validare, comanda poate fi pornită de Task Scheduler DSM la 07:00 Europe/Bucharest, cu jurnal și alertare la codul `2`. În jurul ședințelor se poate reduce intervalul numai după validarea surselor. Nu configura simultan un scheduler NAS și unul GitHub pentru același volum/colector.

Arhiva nu este backup. Înainte de funcționare permanentă sunt necesare backup separat și probă de restaurare a SQLite împreună cu `blobs/`, `text/` și `receipts/`.

## Execuție curentă — Windows

Decizia proprietarului din 23 octombrie 2026 înlocuiește NAS-ul cu MCLENOVO. Urmează [instalarea nativă pe Windows](../../deploy/windows/ramnicu/README.md). Starea verificată și blocajele sunt în [checkpointul Windows](../../strategy/checkpoints/ramnicu-windows-20261023.json). Pachetele NAS rămân doar istoric.
