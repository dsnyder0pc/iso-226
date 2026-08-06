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

**Deploy `dist/`, never `ui/`.** The `index.html` in this directory is Vite's
development entry: it points at `/src/main.tsx`, which no browser can execute,
so serving this directory gets you a blank page and a 404 for a TypeScript
file. Only `npm run build` produces something servable.

`dist/` is a plain `index.html` plus one JavaScript and one CSS file, about
500 KB in total. Copy it anywhere that serves static files:

```bash
rsync -a --delete dist/ user@host:/var/www/iso226-ui/
```

The trailing slash on `dist/` puts those three files at the target root rather
than in a `dist` subdirectory. Nothing else belongs on the server — not
`node_modules` (142 MB), not `src/`, not this file.

An nginx `root` pointing at that directory is the entire server configuration.
Asset URLs are relative, so the page works from a subdirectory of a host as
happily as from its root, and from a pages site.

It does **not** work from a `file://` path — browsers refuse to load ES module
scripts from a null origin, so the page comes up blank. Any static server will
do instead, including `npm run preview` or `python -m http.server --directory
dist`. (Verified, not assumed: the file:// attempt renders an empty document.)

## Links

The page's state is in the address bar, under the same two parameter names the
HTTP API takes and with the same meanings:

```
https://example.org/ui/?level=71&reference=80
```

`level` is the measured listening level; `reference` is the level the recording
was mastered for. The address bar is rewritten as the slider moves (on a short
delay, and with `replaceState`, so a drag does not become thirty entries of
browser history), and the share button copies it — or opens the platform share
sheet on the browsers that have one.

A link carries both numbers rather than the offset that actually keys the data.
Sending the offset would silently re-target the link at whatever reference the
recipient had set; sending both says what the sender was looking at and leaves
the recipient free to change it.

A parameter that is missing, unparseable, or outside what the controls
themselves accept is ignored in favour of the default, per field. It is not
clamped: quietly showing a different level from the one the link names would be
worse than ignoring the link. `npm run check:share-links` round-trips every
level in the grid and a set of malformed queries.

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
  url.ts      the page's state as a link; pure, so a script can round-trip it
scripts/
  check-exports.ts      diffs the CamillaDSP emitter against REW/*.yml
  check-suggestions.ts  every level offered instead of a refusal is servable
  check-share-links.ts  a shared link reopens on the level it was shared from
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
