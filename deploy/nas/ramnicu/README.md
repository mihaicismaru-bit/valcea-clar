# Rulare pilot pe Synology

Instalarea a fost incercata pe NAS la 16 octombrie 2026: proiectul izolat exista,
dar build-ul s-a blocat inainte de pornirea colectorului. Vezi
[raportul DSM](DSM-ACCESS-20261016.md) pentru sanatate, stocare, inventar si erorile exacte.
Colectarea reala si persistenta volumului nu sunt inca validate.

`compose.dsm.yml` pastreaza ultima configuratie incercata prin editorul DSM,
cu sursa fixata la commit si volum Docker numit, separat pe proiect. Este
experimentala: ruta Git cere un executabil absent pe NAS, iar ambele rute de
arhiva remote incercate au esuat cu `invalid tar header`. Nu o considera o
reteta verificata. Pentru reluare, transfera sursa intr-un context local pe NAS
sau importa o imagine construita si verificata separat. Nu sterge volumele.

Reteta de mai jos foloseste un checkout local si un director persistent bind:

1. Verifica sanatatea NAS-ului, spatiul liber si Container Manager.
2. Creeaza un director persistent local si verifica scrierea cu UID/GID alese.
3. Seteaza VALCEA_CLAR_DATA_DIR la calea absoluta a directorului. Seteaza VALCEA_CLAR_UID si VALCEA_CLAR_GID dupa contul de serviciu verificat pe NAS.
4. Din acest director: `docker compose build`, apoi `docker compose run --rm ramnicu-collector`.
5. Verifica `ramnicu-valcea/latest_run.json`, SQLite si originalele din `blobs/`.

Nu seta o programare permanenta pana cand proba live nu trece si inventarul surselor nu este verificat. Containerul este oneshot: nu se reporneste continuu. Nu exista credentale de publicare sau model AI in imagine. PDF-urile scanate raman NEEDS_OCR; poppler extrage numai textul disponibil.

Pentru oprire nu exista un daemon propriu. O rulare poate fi terminata; blocarea OS se elibereaza, iar urmatoarea rulare continua frontiera persistenta. Backup-ul trebuie facut coerent cu SQLite inchis sau prin API-ul SQLite de backup, impreuna cu originalele si textele.
