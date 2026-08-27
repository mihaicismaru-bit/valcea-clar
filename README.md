# VÂLCEA CLAR — GitHub-first public projection

VÂLCEA CLAR is the standalone static public site served by GitHub Pages. It has no ChatGPT Sites dependency and no CMS bridge.

## Canonical architecture

There is one editorial engine and one public projection:

`sources → mihaicismaru-bit/civora → CIVORA canonical live feed → mihaicismaru-bit/valcea-clar → GitHub Pages → valceaclar.ro`

- **CIVORA (`mihaicismaru-bit/civora`)** owns source discovery, verification, editorial policy, story composition, publication eligibility, provenance and social distribution.
- **This repository (`mihaicismaru-bit/valcea-clar`)** owns deterministic public presentation, local public media, GitHub Pages deployment and public HTTP readback.
- **Google Drive** may preserve project checkpoints/evidence but is not a runtime dependency.
- **ChatGPT Sites is not part of production.**

## Active runtime surface

- `scripts/sync_civora.py` — imports the canonical CIVORA `valcea-clar/site/runtime/live-feed.json` and projects it into `content/articles.json`.
- `content/` — public presentation inputs; editorial story authority remains CIVORA.
- `media_source/` + `content/media.json` — curated local public media; remote images are never hotlinked into `<img>`.
- `scripts/build.py` — deterministic static renderer.
- `scripts/enrich_metadata.py` — deterministic `NewsArticle`, Open Graph/Twitter and search-discovery metadata for the generated artifact.
- `scripts/verify.py` — fail-closed route/media/metadata/public-contract validation.
- `_site/` — generated output, never canonical source.
- `.github/workflows/civora-sync.yml` — hourly CIVORA sync, build, metadata enrichment, self-healing GitHub Pages deploy and live readback.
- `.github/workflows/quality.yml` and `pr-validation.yml` — validate the public projection only.

The former standalone `newsroom/`, source registry, candidate engine and auto-publisher have been removed. Do not recreate editorial execution in this repository; editorial changes belong in CIVORA.

## Editorial continuity

Each canonical public cycle:

1. reads the current CIVORA feed;
2. refuses malformed, empty or domain-mismatched input;
3. projects all canonical stories into the public schema;
4. preserves only registered local media;
5. runs unit tests, static build, metadata enrichment and verification;
6. compares the expected canonical lead with `valceaclar.ro`;
7. deploys when canonical content changed, public readback is stale, or the presentation code changed;
8. requires HTTP readback of both homepage and lead story;
9. persists projection state only when canonical input changed.

A repository update is not considered publication until public HTTP readback passes.

## Local validation

```bash
python3 -m unittest discover -s tests -v
python3 scripts/sync_civora.py
python3 scripts/build.py
python3 scripts/enrich_metadata.py
python3 scripts/verify.py
python3 -m http.server 8000 -d _site
```

## Production

GitHub Pages is the production host for `valceaclar.ro`. The canonical sync workflow owns routine deploys. The manual Pages workflow remains only as a recovery path.
