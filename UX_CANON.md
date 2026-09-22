# VÂLCEA CLAR — UX CANON

Status: implementation contract for the public site.

## Reference model

VÂLCEA CLAR uses a **Washington Post–inspired editorial information architecture**, adapted for a local Romanian publication. This is a functional reference, not a visual clone and not a reuse of protected brand assets.

## Binding principles

1. **continuous_story_first** — the homepage is a continuously updated editorial front page, not a generic card grid.
2. **Editorial hierarchy before symmetry** — one clear lead, a latest-news rail, then a chronological/local stream and section blocks.
3. **Strong masthead** — VÂLCEA CLAR is visually dominant; navigation is secondary and section-led.
4. **Fast scanning** — kicker, headline, dek, timestamp and source context must be legible without opening every story.
5. **Local relevance** — section navigation follows the actual Vâlcea newsroom taxonomy.
6. **Evidence visible** — article pages preserve explicit sources/documents and clear factual framing.
7. **Mobile is editorial, not collapsed desktop** — hierarchy survives on small screens; navigation can scroll horizontally and story order stays intact.
8. **No fake popularity metrics** — do not invent “most read”, engagement, live status or audience counts without real telemetry.
9. **No decorative remote media** — public `<img>` assets remain local, registered and validated.
10. **Fail closed** — UX changes must not weaken newsroom publication gates, media provenance checks, route validation or production deployment controls.

## Homepage order

1. edition/update status
2. short headline strip (“Pe scurt”)
3. lead story + latest rail
4. continuous local stream (“În Vâlcea, acum”)
5. editorial section blocks
6. footer/legal

## Article page order

1. return/navigation context
2. section kicker
3. headline
4. dek
5. newsroom + timestamp
6. share controls
7. contextual media and caption when available
8. article body
9. sources and documents
10. return to news stream

## Product-aware article UX

**Section and editorial product are separate axes.** A story may belong to ECONOMIE, ADMINISTRAȚIE or CULTURĂ while its reader-facing product is PE SCURT, CLARIFICĂM, VERIFICAT, CE URMEAZĂ, VÂLCEA AZI, WEEKEND CLAR, DOSAR, UNDE IEȘIM, PROFIL/OAMENI, ANCHETĂ or PAMFLET/SATIRĂ.

The masthead, typography system and core navigation stay recognizably VÂLCEA CLAR. Product differences change editorial grammar, not brand identity:

- **PE SCURT** — compact reading measure, essential context first.
- **CLARIFICĂM / VERIFICAT** — evidence-forward signpost and stronger source treatment.
- **CE URMEAZĂ** — follow-up framing, deadlines and next steps when supplied by CIVORA.
- **VÂLCEA AZI** — default continuous-news treatment.
- **WEEKEND CLAR / UNDE IEȘIM** — service-oriented treatment for plans, events and useful details.
- **DOSAR / ANCHETĂ** — long-form measure, stronger hierarchy, document/source emphasis.
- **PROFIL/OAMENI** — portrait-led treatment when verified media exists.
- **PAMFLET/SATIRĂ** — unmistakable format disclosure; satire never visually masquerades as straight news.

The public projection must prefer an explicit CIVORA product field. Fallback inference is conservative and may never upgrade an ordinary story into ANCHETĂ, VERIFICAT or another higher-claim format without a canonical signal.

## Visual language

- white/neutral editorial canvas
- black typography and rules
- restrained VÂLCEA CLAR accent color
- serif headlines and long-form reading text
- sans-serif utility/navigation text
- dense but readable desktop hierarchy
- simplified single-column mobile flow

## Anti-regression contract

The generated homepage must expose `data-layout="continuous-story-first"` and use the editorial classes exercised by `tests/test_site_ux.py`. A renderer that falls back to a generic `hero + grid` homepage violates this canon even if CSS still contains editorial classes.
