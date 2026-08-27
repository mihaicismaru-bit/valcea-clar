# VÂLCEA CLAR — GitHub-first public projection

VÂLCEA CLAR is the standalone static public site served by GitHub Pages. It has no ChatGPT Sites dependency and no CMS bridge.

## Canonical architecture

There is one editorial engine and one public projection:

`sources → mihaicismaru-bit/civora → CIVORA canonical live feed → mihaicismaru-bit/valcea-clar → GitHub Pages → valceaclar.ro`

- **CIVORA (`mihaicismaru-bit/civora`)** owns source discovery, verification, editorial policy, story composition, publication eligibility, provenance and social distribution.
- **This repository (`mihaicismaru-bit/valcea-clar`)** owns the deterministic public presentation, local public media bundle, GitHub Pages deployment and public HTTP readback.
- **Google Drive** may preserve project checkpoints/evidence but is not a runtime dependency.
- **ChatGPT Sites is not part of production.**

## Active public path

- `scripts/sync_civora.py` — imports the canonical CIVORA `site/runtime/live-feed.json` and deterministically projects it into `content/articles.json`.
- `content/` — public presentation inputs. Editorial story authority remains CIVORA.
- `media_source/` + `content/media.json` — curated local public media; remote images are never hotlinked into `<img>`.
- `scripts/build.py` — deterministic static build.
- `scripts/verify.py` — fail-closed route/media validation.
- `_site/` — generated output, never canonical source.
- `.github/workflows/newsroom.yml` — hourly CIVORA sync, build, self-healing Pages deploy and live readback.
- `.github/workflows/quality.yml` / `pr-validation.yml` — validate the CIVORA projection rather than a second newsroom.

The order delivered by the CIVORA feed is authoritative for the public homepage. The importer projects that order into presentation priority so an old high-priority dossier cannot pin the lead above newer canonical stories.

## Editorial continuity

The public workflow runs hourly. Each cycle:

1. reads the current CIVORA canonical feed;
2. refuses malformed/domain-mismatched/empty feeds;
3. projects all canonical stories into the public schema;
4. preserves only already-registered local media;
5. runs unit tests, build and verification;
6. compares the expected canonical lead with `valceaclar.ro`;
7. deploys to GitHub Pages when content changed **or** the public site is stale;
8. requires HTTP readback of both homepage and lead story;
9. persists projection state only when canonical input changed.

A repository update is not considered publication until the public readback passes.

## Legacy cleanup

The former standalone newsroom implementation under `newsroom/` and the old `scripts/newsroom*.py` / `scripts/auto_publish.py` path is **deprecated and has no scheduled execution authority**. It remains temporarily for reconciliation evidence and will be deleted after public parity/readback has been demonstrated on the CIVORA-fed path.

Do not re-enable a parallel source registry, candidate engine or auto-publisher in this repository. Editorial changes belong in CIVORA.

## Local validation

```bash
python3 -m unittest discover -s tests -v
python3 scripts/sync_civora.py
python3 scripts/build.py
python3 scripts/verify.py
python3 -m http.server 8000 -d _site
```

## Production

GitHub Pages is the production host for `valceaclar.ro`. The hourly canonical workflow owns routine deploys. The manual Pages workflow remains only as a recovery path.
