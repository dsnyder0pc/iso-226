# The browser UI

A single page for choosing a listening level and seeing what the compensation
does. Drag the slider and the response redraws immediately: every level's
curves were computed in advance by the same Python that generates the presets,
so the browser is looking things up, not calculating them.

## npm is a build tool here, not a server

There is no backend. `npm` is needed on the machine that *builds* the page —
the sources are TypeScript and Tailwind, which browsers cannot load directly —
and on no machine that serves it.

```bash
npm install     # first time; commit the package-lock.json it writes
npm ci          # afterwards, from that lockfile
npm run dev     # http://localhost:5173, with hot reload
npm run verify  # tsc --noEmit, then the export golden check
npm run build   # writes dist/
```

`dist/` is a plain `index.html` plus one JavaScript and one CSS file. Copy it
anywhere that serves static files:

```bash
rsync -a dist/ user@host:/var/www/iso226-ui/
```

An nginx `root` pointing at that directory is the entire server configuration.
Asset URLs are relative, so the page works from a subdirectory of a host as
happily as from its root, and from a pages site.

It does **not** work from a `file://` path — browsers refuse to load ES module
scripts from a null origin, so the page comes up blank. Any static server will
do instead, including `npm run preview` or `python -m http.server --directory
dist`. (Verified, not assumed: the file:// attempt renders an empty document.)

## Where the numbers come from

Two generated files, imported directly from `../web` — the same bytes the HTTP
API serves. There is no copy in this directory, deliberately, and
`tests/test_curves.py` fails if one appears.

| file | what it carries |
| --- | --- |
| `web/presets.json` | the published filters, headroom and residual per offset |
| `web/curves.json` | the ISO target and each band's response, sampled on the grid the optimizer fitted against |

Both come out of one run of `precompute_presets.py`. Change the maths and you
must rerun it, or the page will draw filters the repository does not publish;
the Python suite fails when they diverge.

The browser sums band curves (decibels add, because magnitudes multiply) and
subtracts a target. That is the whole of its arithmetic — it evaluates no
biquads and interpolates between no levels. Presets exist at whole-decibel
offsets, so the slider steps in whole decibels rather than tweening between
values that were never fitted.

## Layout

```
src/
  data/       the two artifacts, typed and differenced once per level
  plot/       scales, ticks and path strings, memoized per offset
  components/ the page
  export/     CamillaDSP, Equalizer APO, Roon, CSV, JSON emitters
  audio/      pink-noise preview through WebAudio
scripts/
  check-exports.ts      diffs the CamillaDSP emitter against REW/*.yml
  check-suggestions.ts  every level offered instead of a refusal is servable
```

`src/export/formats.ts` is the only place the UI reimplements a repository
format rather than reading one, which is why `npm run check:exports` exists.
`check-suggestions.ts` is the UI's copy of the rule the API's
`test_every_suggested_level_can_actually_be_served` enforces; both scripts have
already caught a real bug — a negative zero that JavaScript prints without its
sign, and a refusal that offered the user the level that had just failed.
The audio preview is approximate on purpose: WebAudio runs at the output
device's sample rate with the browser's own biquads, while these filters are
designed and verified at 44.1 kHz.
