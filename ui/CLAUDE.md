# CLAUDE.md — `ui/`

The static browser page: Vite + React + TypeScript, no backend. These notes
load when Claude works with files under `ui/`; the repository-wide notes are in
the root `CLAUDE.md`, which is where the invariants, the ISO data rules and the
code-quality bar live.

- **The plot grid *is* the design grid.** `web/curves.json` samples on
  `np.concatenate(design_grid())` — the 182 points the optimizer fitted
  against, 10 Hz–20 kHz. That identity is load-bearing three times over: the
  stored target is `build_target(comp).target` including its flat-held
  extrapolation, so the page can show the held regions instead of cropping
  them; `in_band` is the same slice the objective minimizes over, so the
  residual the curves imply *is* the published `max_residual_db` rather than
  something near it; and there is no second definition of where the ISO data
  stops. Do not resample it onto a rounder grid for the plot.
- **No DSP in the browser.** Bands are stored separately and summed in
  JavaScript — magnitudes multiply, so decibels add, and the sum is the
  cascade response exactly (checked to 5e-15). The page adds decibels and
  subtracts a target; it evaluates no biquads. This is deliberate: the RBJ
  coefficients already shipped a sign error once, and a second implementation
  of them in another language is a second place for that to happen. The
  predecessor of this UI drew a *fabricated* target — `response + sin(...)` —
  which no test could have caught, because nothing tied its picture to the
  numbers. `tests/test_curves.py` is that tie.
- **`ui/` imports `web/*.json`; it must never hold a copy.** The prototype
  kept a byte-identical duplicate of `presets.json` in its own tree.
  `test_the_ui_keeps_no_copy_of_the_generated_data` forbids it.
- `src/export/formats.ts` is the one place the UI reimplements a repository
  format rather than reading one, so `npm run check:exports` diffs its
  CamillaDSP output against every committed `REW/*.yml`. It is an npm script,
  not a pytest test, for the same reason Flask is absent from the root
  `requirements.txt`: the Python suite must not require a JavaScript
  toolchain. The pass-through preset is skipped there — `REW/` ships five
  zero-gain bands so the file stays a loadable config, while the API
  publishes it as no filters at all.
- **JavaScript prints a negative zero without its sign.** `(-0).toFixed(1)`
  is `"0.0"`, where Python gives `-0.0`, and three committed configs carry a
  band that rounds a hair below zero. `fixed()` in `src/format.ts` puts the
  sign back; every gain and Q in every emitter goes through it. A Python
  emulation of the emitter matched all 13 files and missed this — only
  running the real thing found it.
- **Refusal messages name a level twice**, the one that failed and the one to
  try instead, so `parseRefusal` reads only the text after `Try one of:`.
  Reading the first match offered the user 58 dB as the way out of 58 dB
  being unavailable. `npm run check:suggestions` is the UI's copy of
  `test_every_suggested_level_can_actually_be_served`; `src/data/refusal.ts`
  is import-free so that script can run it under Node.
- **The page does not work from `file://`** — the entry is an ES module and
  browsers block those from a null origin, so it renders blank. Verified, not
  assumed. Any static server works, including `npm run preview`. What gets
  deployed is `ui/dist/`, never `ui/`: the source `index.html` is Vite's dev
  entry and points at `/src/main.tsx`.
- **Deep links use `?level=` and `?reference=`** — the API's parameter names,
  with the API's meanings, so a shared link translates to a curl command by
  inspection. Not the offset, even though the offset is what keys the data:
  sending it would re-target a shared link at the recipient's reference
  instead of the sender's. A bad parameter falls back to the default per
  field and is never clamped, because showing a different level from the one
  the link names is worse than ignoring the link. `src/url.ts` is import-free
  so `npm run check:share-links` can round-trip it under Node.
- Both vertical scales on the plot are fixed across the whole ladder rather
  than fitted to the level on screen, so dragging the slider shows the
  correction growing and the residual worsening at the quiet end. 60 dB
  *looking* worse than 70 dB is the point.
- **The view is 20 Hz–20 kHz; the data is not.** The window matches the
  figures in `images/` that the PEQ tables embed, so a listener comparing
  the page against a preset's own plot sees the same picture. It crops
  exactly at `in_band`, whose first index is 20 Hz to within 4e-15, so the
  sub-20 Hz extrapolation block comes off whole and nothing measured is
  touched — the residual is still computed over the optimizer's own slice.
  What it stops showing is the sub-20 Hz overshoot described under the
  headroom invariant below; that is deliberate and matches `images/`.
- **The response and the residual are two figures, not two panels of one.**
  Separate cards, separate `<svg>`s, each with its own vertical scale, its
  own frequency axis and its own legend — `ResponsePlot.tsx` and
  `ResidualPlot.tsx`, with the chrome they share in `PlotParts.tsx`. They
  were stacked under a single axis and a single legend until a reviewer read
  the pair as one graph: two meanings of "dB" under one key list, and the
  only frequency labels on the page sitting beneath the *lower* figure, so
  identifying a feature on the response meant tracking down past the
  residual to find out what frequency it was at. What the two still share is
  `xOf` — same viewBox width, same margins, same log mapping, so the cards
  stack in register — and the crosshair, which `Plots.tsx` owns for that
  reason. The hover index lives in `Plots` and not in `App` so that a
  pointer crossing a figure re-renders two figures and not the metrics, the
  filter table and the export panel below them. The note explaining that the
  residual is measured on the published, rounded values moved out of
  `MetricsPanel` at the same time: it was describing a figure two panels
  away, with the stat grid in between.
- **The ISO target is warm; everything in the response family is cool.**
  `--color-target` is amber (#fbbf24), not the blue-grey it was — the same
  reviewer could not reliably separate a thick #94a3b8 target from a #818cf8
  response, which is one hue family distinguished only by a doubling in
  width. Hue now carries it and width reinforces it, which is what a small
  screen and a red-green-blind reader need. Per-band traces are dashed for
  the same reason: they are components of the response, so they stay in the
  accent colour and separate on dash instead. The residual figure's ±max
  lines went slate when amber moved, so amber means one thing per page.
- **The response figure adds the headroom; the residual figure must not.**
  Both traces on the response are drawn with the preamp applied, against
  a 0 dBFS clipping line and a dotted flat reference, exactly as
  `plot_frequency_response` draws the figures in `images/`. This is not
  cosmetic: without it a compensation curve sits almost entirely *above*
  zero and reads as a proposal to boost and clip, when what it asks for is
  attenuation everywhere except the extremes. The residual is the difference
  of two curves, so the preamp cancels out of it — shifting that figure too
  would be wrong, and the published `max_residual_db` is measured on the
  cascade alone. Per-band traces are drawn from the flat reference, so a
  band's distance from that line is its contribution and those distances
  still sum to the response's; shifting each band by the whole preamp would
  not. A refused level has no published headroom, so it is drawn against the
  headroom it *would* need, which is the reason it was refused.
- **The type floor is 14px (`text-sm`); running prose is 16px
  (`text-base`).** The audience is listeners, not developers — the owner puts
  the median age nearer 60 than 30 — and the 10–11px captions this page
  shipped with were legible only by leaning in. The plot's legend was missed
  entirely for that reason, and read as unlabelled traces. `text-xs` and
  `text-[10px]`/`text-[11px]` are therefore absent from `ui/src`; the rule is
  written down at the top of `src/index.css`. The exception is text inside
  the plot's `<svg>`, sized in viewBox units, which scales with the figure
  and not with the type scale — it is still 10–11 units and does shrink on a
  narrow window.
- **The preview's bypass removes the bands and moves the preamp to
  `bypassHeadroomDb`.** Which, since the A/B is matched at 1 kHz, is the
  same number as `headroomDb` at every rung but 83→60 — so in practice the
  preamp now stays put and the bands are the whole change. **Do not
  "simplify" this to reading `headroomDb`.** The page must publish whatever
  the generator published, and this field is where a future revision of the
  match would arrive; hard-coding the identity would silently ignore it, and
  would already be wrong at 83→60. This went the other way once: a 500 Hz
  match shipped on 2026-08-09 making the two differ by 0.3–1.2 dB down the
  ladder, and was falsified the same day — see the bypass invariant below.
  `update` reads the bypass flag off the graph rather than React state,
  because a stale closure there would drag the slider's gain onto the wrong
  side of the comparison. The plot's dotted flat line stays at the preamp:
  it is the datum the per-band traces are measured from. The graph
  allocates one biquad per published band up front rather than one per
  filter, so the slider can move between any two levels — including onto the
  pass-through rung, which has no filters — without a rebuild. An unused
  slot must be set to **`peaking` at 0 dB**, not merely to 0 dB: a fresh
  `BiquadFilterNode` is a lowpass at 350 Hz, and `gain` does nothing to a
  lowpass.
- **Nothing above the figure may depend on the preview state.** The "Hearing
  …" chip lives among the plot's legend keys, below the `<svg>`, and it
  belongs there for layout rather than taste: in the plot's *header* it grew
  that row from 20px to 30px when the preview started — a `text-sm` row
  against a `px-3 py-1` pill — so the plot dropped 10px out from under the
  pointer, and at narrow widths the row wrapped instead and the drop became a
  whole line. Below the figure the row can appear, disappear and rewrap for
  free. It reads as one more key anyway, since it names a trace drawn beside
  it. The page header has the same shape of problem and still has it: it
  gains the bypass button while playing, and being `sticky`, a wrap there
  moves the whole page.
- **The page's closing block is a summary; the README is the document.** The
  footer carries the four-step workflow and three short notes, in two
  columns, and links the rest to `README.md#using-the-web-app`. It was four
  dense paragraphs, which at readable type became a wall of text. New
  explanation belongs in that README section, not appended here — a listener
  opens this page to get a filter set out of it, not to read about it. The
  masthead line reads the same way: it says what the filters *do*, in the
  reader's terms, rather than reciting the edition and the band count, which
  are already in the legend, the metrics and the footer.
