# VÂLCEA CLAR — GitHub-first public projection

VÂLCEA CLAR is the standalone static public site served by GitHub Pages. It has no ChatGPT Sites dependency and no CMS bridge.

## Current publishing status

As of 30 October 2026, the CIVORA Vâlcea Clar tree is no longer present in its main branch. The public repository's `content/articles.json` is the editorial source for the existing Pages workflows. CIVORA synchronization scripts are retained for reference and are not run by production; do not reactivate them without reconciling ownership and preventing overwrites. Existing article, media and Local Life inputs remain in this repository.

## Historical architecture

The former editorial engine and public projection were:

`sources → mihaicismaru-bit/civora → CIVORA canonical live feed → mihaicismaru-bit/valcea-clar → GitHub Pages → valceaclar.ro`

- **CIVORA (`mihaicismaru-bit/civora`)** owns source discovery, verification, editorial policy, story composition, publication eligibility, provenance, visual provenance and social distribution.
- **This repository (`mihaicismaru-bit/valcea-clar`)** owns deterministic public presentation, build-time delivery of approved media, GitHub Pages deployment and public HTTP readback.
- **Google Drive** may preserve project checkpoints/evidence but is not a runtime dependency.
- **ChatGPT Sites is not part of production.**

## Active runtime surface

- `scripts/sync_civora.py` — imports the canonical CIVORA `valcea-clar/site/runtime/live-feed.json`, projects it into `content/articles.json`, and carries only `VERIFIED` non-synthetic visual provenance into the presentation contract.
- `content/` — public presentation inputs; editorial story and visual authority remain CIVORA.
- `media_source/` + `content/media.json` — curated local public media already owned by this repository.
- `scripts/media_assets.py` — reconstructs curated media and mirrors verified CIVORA visuals into the generated Pages artifact at build time. Reader-facing `<img>` elements therefore use local `/media/...` assets rather than runtime hotlinks; `_site/media/provenance.json` preserves the CIVORA origin, source, rights basis, credit, license, hash and delivery mode.
- `scripts/build.py` — deterministic static renderer.
- `scripts/enrich_metadata.py` — deterministic `NewsArticle`, Open Graph/Twitter and search-discovery metadata; image metadata is emitted only for media actually materialized in the artifact.
- `scripts/verify.py` — fail-closed route/media/metadata/public-contract validation.
- `_site/` — generated output, never canonical source.
- `.github/workflows/civora-sync.yml` — hourly CIVORA sync, build, metadata enrichment, self-healing GitHub Pages deploy and live readback.
- `.github/workflows/quality.yml` and `pr-validation.yml` — validate the public projection only.

The former standalone `newsroom/`, source registry, candidate engine and auto-publisher have been removed. Do not recreate editorial execution in this repository; editorial changes belong in CIVORA.

## Historical editorial continuity

Before the source was moved, each canonical public cycle:

1. reads the current CIVORA feed;
2. refuses malformed, empty or domain-mismatched input;
3. projects all canonical stories into the public schema using freshness-first presentation ordering;
4. accepts visual instructions only when CIVORA marks them `VERIFIED` and non-synthetic;
5. mirrors those approved visuals into the Pages artifact at build time while preserving origin/rights provenance;
6. runs unit tests, static build, metadata enrichment and verification;
7. compares the expected canonical lead with `valceaclar.ro`;
8. deploys when canonical content changed, public readback is stale, or the presentation code changed;
9. requires HTTP readback of both homepage and lead story;
10. persists projection state only when canonical input changed.

A repository update is not considered publication until public HTTP readback passes. A visual is not considered publicly delivered merely because it exists in CIVORA metadata; its public article must contain an actual image and the generated media provenance must link the local mirror back to the canonical CIVORA visual.

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

GitHub Pages is the production host for `valceaclar.ro`. The existing scheduled and manual workflows build the repository's current editorial projection, verify the site and deploy with public readback. Editorial updates use reviewed changes to `content/articles.json`; do not run the retired CIVORA sync against the local source.
