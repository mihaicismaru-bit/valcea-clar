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
