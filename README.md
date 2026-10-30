# VÂLCEA CLAR — site public

Site-ul static este publicat prin GitHub Pages la https://valceaclar.ro/.

## Sursa de publicare

Din 30 octombrie 2026, `content/articles.json` este sursa editorială a site-ului; `content/events.json`, `content/local_life.json` și resursele media păstrează datele existente. Articolele se adaugă prin schimbări revizuite, cu surse identificabile, id stabil și `current_story_ids` explicit. Articolele care nu mai sunt actuale rămân disponibile în arhivă.

Workflow-urile Pages existente construiesc și verifică datele din acest repo. Sincronizarea CIVORA nu mai este executată: vechiul director Vâlcea Clar lipsește din CIVORA main. Scripturile istorice rămân în repo, dar nu trebuie reactivate fără verificarea proprietății și prevenirea suprascrierii datelor locale. O singură cale de publicare folosește grupul de concurență `valcea-clar-civora-public-sync`.

## Validare

```bash
python3 -m unittest discover -s tests -v
python3 scripts/build.py
python3 scripts/history_projection.py --self-test
python3 scripts/history_projection.py
python3 scripts/enrich_metadata.py
python3 scripts/verify.py
```

Publicarea este completă numai după verificarea directă a paginii articolului, a primei pagini, a arhivei, a Local Life și a media. La nevoie, revenirea se face prin revert și o versiune Pages precedentă verificată, ținând cont de modificările apărute ulterior.
