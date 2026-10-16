# Local real-source probe — 16 October 2026

These runs executed on the Windows workstation while DSM remained unavailable.
They do **not** demonstrate deployment, persistent-volume writes or execution
on NAS, and do **not** validate a complete meeting or urbanism case.

## Runs and extraction fix

The unmodified collector performed 60 bounded requests, saved 60 changed
versions and had no fetch errors. Its receipt is
`ramnicu-live-evidence-receipt.json`. The frontier still had 345 due URLs;
60 versions initially required extraction review. Live HTML revealed a parser
bug: a `<main>` containing only whitespace took precedence over useful visible
body text. The fix in `676fea8` falls back to the visible body when main text
is empty, while still excluding navigation/footer text. A regression test was
added and all 15 module tests passed. The original receipt is preserved as
generated, without rewriting its historical extraction counts.

After the fix, a focused run requested the two parent pages and all 8 linked
PDFs in the selected source inventories. Its receipt is
`ramnicu-focus-evidence-receipt.json`. It saved the two parent pages with text
extracted; all 8 PDF attempts were blocked before fetching by the collector's
robots policy. `published=0` in both receipts. The focused config used explicit
seeds with depth zero; depth-limit entries refer to links outside the bounded
target list and are preserved in the receipt, not hidden as successful coverage.

Targets in `focus-inventory.json`:

- Meeting convened for 16 September 2026: 4 PDF links (convocation and 3 draft
  decisions). Full post-meeting minutes, votes and adopted decisions have not
  been cross-checked; this is only a convocation-package inventory.
- Urbanism draft item 23 on the 23 July 2026 convocation page: transformation
  of office space into service dwellings at Calea lui Traian 224–224 A. Four
  PDFs are linked: draft PUZ/RLU, location plan, regulations/urban arrangement,
  and existing situation. No PDF was collected, visually reviewed or validated.

## Demonstrated source restriction

`official-robots.txt` is the live `text/plain; charset=utf-8` response obtained
using the collector's configured User-Agent, `ValceaClarResearch/0.1
(+https://valceaclar.ro)`. It explicitly contains:

```text
User-agent: *
Disallow: /documente/
```

A separate curl request with its default identity received an HTML WAF rejection;
that response was not used to infer robots permission. The collector identity
received the actual plaintext rule, explaining all 8 focused PDF blocks.
Neither robots controls nor WAF were bypassed. An official alternative permitted
source or appropriate collection permission remains necessary for these PDFs.
This source restriction is independent of the DSM outage.

## Provenance and limitations

`originals-manifest.json` records 62 version entries across the two local
archives, with source/final URL, SHA-256, MIME type, first-seen time, extraction
state, relative blob/text paths and byte size. Every listed original was
rehash-checked against its recorded SHA-256. The two archives may contain the
same parent-page content; 62 entries does not mean 62 distinct documents.

Raw originals, texts and SQLite remain in the task's `work/ramnicu-live-evidence`
and `work/ramnicu-focus-evidence` directories; they are not committed here.
This manifest and the receipts persist the audit results, not a portable backup
of the local evidence archives. Both archives must be copied coherently with
SQLite closed or through SQLite backup before moving them to another host.

The source ZIP prepared for NAS is now `ramnicu-nas-source-676fea8.zip`, replacing
the prior pre-fix ZIP. See `deploy/nas/ramnicu/source-transfer-676fea8.json`.
No upload or new NAS build occurred in this retry. Publication remains off;
existing NAS services and CIVORA workflows remain untouched.
