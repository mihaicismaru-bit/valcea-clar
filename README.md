# VÂLCEA CLAR — clean GitHub-first site

Standalone static news publication repository. No ChatGPT Sites, no CMS bridge, no runtime dependency on Google Drive, and no remote images in `<img>`. The local guide / „Unde ieșim” is intentionally out of scope until the automated newsroom is finalized.

## Architecture

- `content/` — canonical editorial/site data
- `media/` — curated, optimized local images committed to Git
- `scripts/build.py` — deterministic stdlib static build
- `scripts/verify.py` — fail-closed public-media and route validation
- `_site/` — generated output (not canonical source)
- `.github/workflows/pages.yml` — GitHub Pages build/deploy

## Local validation

```bash
python3 scripts/build.py
python3 scripts/verify.py
python3 -m http.server 8000 -d _site
```

## Deployment

Push to `main`, enable GitHub Pages with **Source: GitHub Actions**, configure `valceaclar.ro` as the custom domain, then point DNS to GitHub Pages. Do not reconnect a Sites presentation layer.

## Migration policy

Drive may remain an editorial archive/source inbox, but anything displayed publicly must first be copied into `media/`, attributed in `content/media.json`, and pass `scripts/verify.py`.

## Current scope

Newsroom first: automated news intake, editorial verification, article generation, editions, media provenance, publishing and distribution. Local-guide features are deliberately deferred.

## Newsroom Core v1

The active automation is deliberately smaller than the legacy CIVORA surface:

1. `newsroom/sources.json` — one canonical source registry (T1/T2 tiers).
2. `scripts/newsroom_cycle.py` — fetch, normalize, score, cluster/deduplicate and decide.
3. `newsroom/output/` — candidate and readiness queue; this is not public content.
4. `newsroom/state/` — seen URLs and source-health state.
5. `scripts/newsroom_verify.py` — fail-closed policy guard.
6. `.github/workflows/newsroom.yml` — 10-minute radar; persists candidate state only.

Current `publication_mode` is **candidate_only** and `auto_publish.enabled` is **false**. A T1 item may be marked `READY_T1` as a simulation of what would be eligible later, but the workflow has no authority to move it into `content/articles.json`.

Production deployment is also locked: it is manual-only and requires the literal `DEPLOY` confirmation. Normal pushes only run quality checks. The build emits `CNAME` only when `VALCEA_CLAR_PRODUCTION=1`.
