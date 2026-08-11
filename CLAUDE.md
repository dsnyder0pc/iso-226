# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository does

Generates parametric EQ filter sets that compensate for the level-dependence of
human hearing, based on the **ISO 226:2023** equal-loudness contours (third
edition). Output is consumed by REW / CamillaDSP / Roon / miniDSP for real
listening rooms.

## Commands

Every command lives in `CONTRIBUTING.md` — setup, the ISO data files, the
generator, the tests, the linters, the UI build. Do not restate them here. Two
things that section does not say:

**Run the long ones in the background.** `regenerate.py` is ~5.5 minutes and
`precompute_presets.py` ~40 minutes; both will outlast a foreground call. The
fit is seeded (`seed=3`), so a rerun of `precompute_presets.py` reproduces the
committed filters exactly — a refit that changes a single published value means
the maths changed, and the diff is the evidence.

**Environment note:** the project uses a pyenv virtualenv named `iso-226`
(`.python-version`), which auto-activates only inside the project directory.
Running scripts from elsewhere gives `ModuleNotFoundError: No module named
'scipy'`. Use `/home/dsnyder/.pyenv/versions/iso-226/bin/python` explicitly, or
`cd` into the repo first.

## Architecture

- **`iso226_utils.py`** — all shared math.
  - `Compensation(level, reference, scale)`: **the parameter bundle.** A frozen
    dataclass, validated once in `__post_init__`, that defines one compensation
    curve. It travels through target construction, fitting, refusal messages,
    filenames and all three writers, so nothing downstream re-checks a range or
    can transpose a level for a reference. Adding a fourth knob means adding a
    field here, not a parameter to a dozen signatures. This is what the Flask
    work should build from query parameters.
  - `iso226_spl(phon, f_arr)`: ISO 226:2023 Formula (1). Coefficients
    interpolate in **log** frequency. Raises outside 20–90 phon, the range the
    standard defines.
  - `ideal_delta(comp)`: the compensation target — difference of two contours,
    normalized to 0 dB at 1 kHz (`REF_1KHZ_INDEX`), times `comp.scale`.
  - `build_target(comp)`: returns a `FitTarget` NamedTuple of
    `(grid, target, in_band)`. The grid spans 10 Hz–20 kHz; the target is
    **held flat** outside 20 Hz–12.5 kHz where ISO has no data. `in_band`
    selects the ISO-backed region the optimizer's objective minimizes over. It
    is a NamedTuple so it still unpacks positionally where that reads better.
  - `get_biquad_coefs` / `get_filter_response`: RBJ Audio EQ Cookbook biquads,
    cascaded via `scipy.signal.freqz`. Default `fs` is `DESIGN_FS` = 44100.
  - `peak_gain(filters)`: worst peak across `VERIFY_RATES` (44.1/48/96/192 kHz).
  - `ANNEX_B_TOLERANCE_DB` = 0.05 — Table B.1 is printed to 0.1 dB, so this is
    exact agreement. The contour values themselves are ISO's and are **not** in
    the repo: they live in the gitignored `reference/annex_b_2023.py`, supplied
    from `tests/annex_b_reference.py.example` by whoever owns the standard.
    Without them `test_matches_published_annex_b` skips.

- **`loudness-filters.py`** — generator CLI.
  - `_Objective` / `_solve_once` / `_fit_bands`: three concerns kept apart —
    what "error" and "feasible" mean for a band layout, one SLSQP solve, and the
    multistart loop around it.
  - `_Objective`: minimax fit in **epigraph form** (minimize `t` subject to
    `|error| <= t`). Do not "simplify" this back to handing `np.max(np.abs(...))`
    to SLSQP — that function is non-differentiable at the optimum and fits 3–5×
    worse.
  - `calculate_filters(...)`: fits one set of `BAND_COUNT` (5) bands. Returns
    `{'filters', 'error', 'restarts', 'target_met'}`, with `filters` already at
    publication precision and `error` measured from those rounded values.
  - **Multistart selection is on the *published* error, not the raw fit**, and
    an attempt is rejected unless SLSQP converged *and* the returned point
    satisfies every constraint. Both rules matter: scoring on the raw fit let a
    restart win that was better before rounding and worse after, which made the
    62 dB preset 16% worse (0.0986 → 0.1140 dB) when restarts were increased.
    Together they make best-so-far monotonic, so running the search longer can
    never degrade the result — which the target-driven loop depends on.
  - Search stops on the `PUBLISHED_ERROR_TARGET_DB` (0.05) target, on
    `STAGNATION_LIMIT` consecutive non-improving restarts, or at `MAX_RESTARTS`.
    Missing the target is reported, not hidden; 60–65 dB do not reach it and
    that is the honest limit of five bands, not a bug.
  - `publication_round(...)`: frequency to **4 significant figures**, gain and Q
    to 2 decimals. Frequency uses significant figures because its sensitivity is
    fractional — measured per band, the high shelf is the most demanding in the
    set (0.08% at 9.9 kHz, because it carries the gain), while low-gain interior
    peaks tolerate 1–2%. A fixed decimal count is the wrong shape for a column
    spanning three decades. Q is the sensitive parameter by ~20× and sets the
    floor under the whole format; a third gain decimal buys nothing beneath it.
  - `cascade_diagnostics(...)`: worst intermediate stage gain and quantization
    sensitivity. Guards against degenerate near-cancelling band pairs.
  - `check_budget(...)`: refuses over-budget requests with computed `--scale`
    and `--level` suggestions (estimated from the target's magnitude, not from
    the failed fit's peak).

- **`check.py`** — parses the **published, rounded** values back out of the
  Markdown table and plots residual error for the published set. It
  imports `preset_stem` from the generator so both agree on filenames, and
  shells out to generate the preset if that file does not exist yet.

- **`precompute_presets.py` + `web/`** — the HTTP API.
  - A fit takes 20–45 s, which cannot happen inside a request. It does not have
    to: the curve depends on `level - reference`, so the space collapses to one
    offset axis. `precompute_presets.py` fits that grid offline and writes
    `web/presets.json`; `web/app.py` is a dictionary lookup over it.
  - **`web/` must never import NumPy or SciPy.** That is the whole point — 42 MB
    resident against 108 MB, which is what fits a 1 GB droplet. If the API ever
    needs to fit something, the answer is to widen the grid, not to import the
    generator.
  - **There are now three generated artifacts, and nothing keeps them in step
    automatically.** `regenerate.py` writes `PEQ/`, `REW/` and `images/`;
    `precompute_presets.py` writes `web/presets.json` **and** `web/curves.json`
    in one run. Change the math and you must run **both commands**, or the
    website will serve different filters from the ones the repository
    publishes. `test_api_grid_matches_the_committed_presets` fails when the
    tables and the API diverge; `tests/test_curves.py` fails when the two JSON
    artifacts come from different runs, or when a stored curve stops matching
    the filters beside it. Those tests are the only thing standing between a
    maths change and a silently stale page.
  - `web/openapi.yaml` is the contract handed to front-end authors and code
    generators. Its examples are copied from live responses and asserted against
    them by `test_documented_examples_match_live_responses`, which rebuilds each
    example's request from the example itself, so it cannot drift silently
    either. (That assertion was described here long before it existed. It exists
    now; do not let it lapse.)
  - **The grid is fitted wider than it can serve.** The deepest offsets are
    fitted, refused by `check_budget` and stored as refusals, so `OFFSET_MIN/MAX`
    (fitted) and `SERVABLE_MIN/MAX` (usable) are different numbers and mean
    different things. Test against the fitted range — an offset inside it has a
    stored entry whose refusal names the budget it exceeded, which is far more
    use than a range error — but **advertise the servable range**, because that
    is what `/v1/meta` and the spec promise. Quoting the fitted range in a
    message sent callers to levels that were fitted, refused and unavailable;
    `test_every_suggested_level_can_actually_be_served` now holds the API to the
    same rule the CLI's `suggest_alternatives` follows.

- **`ui/`** — the static browser page. Vite + React + TypeScript, no backend.
  Its working notes live in **`ui/CLAUDE.md`**, which loads when you work under
  that directory. Two rules there reach back into this file: the page's data is
  `web/curves.json`, sampled on the optimizer's own design grid, and `ui/` must
  never hold a copy of it.

- **`tests/`** — the suite's working notes live in **`tests/CLAUDE.md`**, which
  loads when you work under that directory. The short version: the tests that
  earn their keep are the ones not sharing code with the thing under test —
  `test_matches_published_annex_b`, the shelf-property tests, and the
  Markdown/YAML round-trips that couple the generator to `check.py`.

### ISO data — no ISO numbers live in this repository

Two separate sets, both gitignored under `reference/`, both supplied by whoever
holds the standard. Do not commit either, and do not "helpfully" inline values
found in a paper, a Wikipedia table or another repository — provenance is the
whole point.

- **Table 1** (`reference/iso226_table1.py`, template
  `tests/iso226_table1.py.example`) — `ISO_AF` / `ISO_LU` / `ISO_TF`, loaded by
  `_load_table1()`. **Nothing runs without it**: no import, no tests, no
  generator. That is the intended behaviour, not a bug to work around.
  `ALPHA_R` and `T_R` are *derived* from its 1 kHz entries rather than restated,
  so there is one source for each number.
- **Annex B** (`reference/annex_b_2023.py`) — verification only; its absence
  skips one test.

`ISO_FREQ` (ISO 266 preferred frequencies) stays committed: it is the R10
preferred-number series, needed to index the columns that are absent.

The loader validates shape, not values — column lengths, plus `ISO_LU` being
0.0 at 1 kHz, which is true by definition since `L_U` is specified relative to
1 kHz. That catches a transcription off-by-one without this repo asserting any
value it does not own.

## Code quality bar

**pylint must reach 10.00/10.** Not "close enough" — the owner's standing
preference is a clean run. The bar, the exact invocation and the reasoning
behind both are in `CONTRIBUTING.md`; what follows is only what that section
does not carry.

The single exception is a fix that would genuinely harm clarity or
maintainability. When that applies:

* disable the check **at the site**, with a comment saying why — never in a
  config file, and never a bare `# pylint: disable=` with no reasoning;
* prefer restructuring over suppressing. See `Compensation` below.

Existing documented exceptions, all deliberate: `wrong-import-position` where
`sys.path` setup or matplotlib's backend selection must precede imports;
`import-outside-toplevel` for the lazy matplotlib import, which costs about a
second and is not needed by most invocations; `redefined-outer-name` in
`conftest.py`, where one pytest fixture requesting another necessarily shadows
the name; `protected-access` in the Table 1 loader tests, which are testing the
loader's contract.

**The score is 10.00.** Run the full command from `CONTRIBUTING.md` — linting
`tests/` on its own reports spurious `import-error`, because the repo root only
lands on the path when the modules are linted together.

**Any Bash added to this repo must pass `shellcheck -S style` cleanly**, which
today means `deploy/install.sh`.

## Invariants — do not break these

- **Everything normalizes to 0 dB at 1 kHz** (`REF_1KHZ_INDEX = 17`). Don't
  reorder `ISO_FREQ` / `ISO_AF` / `ISO_LU` / `ISO_TF`; they are positionally
  aligned to ISO 226:2023 Table 1.
- **Filter type strings** (`'Peak'`, `'Low Shelf'`, `'High Shelf'`) are matched
  literally in `get_biquad_coefs`, written into Markdown cells that `check.py`
  parses back, and mapped in the YAML writer. Changing one requires all three.
- **Per-band gain is capped at ±12 dB** (Roon MUSE PEQ slider; miniDSP is ±16,
  so 12 satisfies both), plus a total-absolute-gain budget and non-overlapping
  per-band frequency ranges. These exist to prevent degenerate solutions with
  two large opposing filters at nearly the same frequency — which measure fine
  end-to-end but overflow intermediate nodes in serial fixed-point DSPs and lose
  their cancellation under host coefficient quantization.
- **`BAND_FC_BOUNDS` is hand-tuned and earns it.** Replacing it with even log
  spacing over the same range costs a factor of five in published error
  (0.027 → 0.133 dB at 83 → 74 dB). Do not "regularize" it.
- **`cascade_diagnostics` inspects frequency-adjacent pairs**, so inserting
  near-zero-gain bands between the real ones silently neutralizes
  `opposing_neighbours`. The old refinement tier did exactly that: the 65 dB set
  read 0.100 across ten bands and 2.023 across the five doing the work. If a
  band count ever changes again, recheck that threshold against real values.
- **No filter band above 12 kHz.** A 16 kHz shelf extrapolates past the ISO data
  with no evidence behind it, and it is where the residual sample-rate
  dependence lives: the previous version's response at 20 kHz ranged from
  +8.44 dB at 44.1 kHz down to +6.32 dB at 192 kHz. (An earlier note here
  claimed a +12.73 dB peak at 192 kHz; that was an artifact of the high-shelf
  coefficient bug, not a real rate effect.)
- **Design and analyse at 44.1 kHz**, verify headroom across all `VERIFY_RATES`,
  and publish the worst case rounded *away from zero* to 0.1 dB (Roon's entry
  precision, and the one field where Roon really is limited to one decimal).
- **The published headroom covers 20 Hz–20 kHz, not the whole design grid.**
  `peak_gain` measures on `logspace(log10(20), log10(20000))`, while the fit
  runs from 10 Hz. A low shelf has not reached its plateau at 20 Hz, so these
  cascades peak *below* the range the headroom is measured over: 23 of the 31
  servable presets exceed 0 dBFS somewhere in 10–20 Hz, worst +0.75 dB at
  83→63 dB, and identical at all four rates because warping is a Nyquist
  effect. The bound is the low shelf's own gain, itself capped at 12 dB.
  **This is known and accepted, not an oversight** — content below 20 Hz is
  rare and inaudible, and the owner has judged it not worth the cost. That
  cost is the reason to think before "fixing" it: measuring from
  `EXTRAP_LOW_HZ` makes 23 presets 0.1–0.8 dB more negative, which rewrites
  every table, config, figure and README value, and pushes 60 dB over the
  12 dB budget so the documented floor moves to 61 dB. The filters themselves
  would not change.
- **The A/B bypass is matched at 1 kHz. Do not re-derive it; theory has lost
  four times.** `MATCH_FREQ_HZ` is `ISO_FREQ[REF_1KHZ_INDEX]` — written as that
  identity, not `1000.0`, because the claim is precisely *match where the
  compensation is defined to be 0 dB*. `match_delta` reads the published
  cascade there; `bypass_headroom` adds it to the headroom, or returns the
  headroom unchanged within `MATCH_NEGLIGIBLE_DB` (0.2), which is what happens
  for 30 of the 31 servable presets. **In effect the bypass preamp is the
  headroom preamp**, and the machinery survives to express *why* and to carry
  the one exception: 83→60, the loosest fit, misses 0 dB at 1 kHz by −0.205 dB
  and publishes −12.1 against a −11.9 headroom. That is not fit error leaking
  in — if the compensated side really plays 0.2 dB quiet at 1 kHz, matching
  there means attenuating the flat side to meet it.

  **The durable finding is the direction of the error, not the frequency.**
  Four stronger rules shipped or were costed and every one *over*-credited the
  restored bass; none under-credited it. BS.1770 asked for 2.4 dB at 83→75 and
  7.6 dB at 83→60; an ISO 226-weighted integral for +0.81 dB at 83→75; a
  500 Hz match for 0.3–1.2 dB down the ladder, and that one was falsified in
  blind listening by a second listener, who preferred the *flat* side at both
  78 and 75 dB for exactly as long as it carried the credit. Matching at the
  response trough or below fails the other way and hands the compensated side
  the advantage. The tests holding this are
  `test_the_match_frequency_is_the_normalization_frequency` and
  `test_match_delta_still_reads_the_cascade_and_not_the_target`, the latter
  standing on the 83→60 values in `tests/test_generator.py::LOOSEST` — without
  it a `match_delta` hard-coded to zero would pass everything else. The owner
  wants this left alone to soak; the narrative was deliberately trimmed out of
  the README and the code comments, so this bullet is the surviving record.
- **Out-of-band regions are constrained, not optimized.** Keep the target
  flat-held below 20 Hz and above 12.5 kHz with `EXTRAP_TOLERANCE_DB`; this is
  what keeps subsonic gain bounded.
- **Preset filenames encode the pair**: `filter_<ref>_to_<level>_s<scale>`,
  built by `preset_stem()` in `loudness-filters.py` and imported by `check.py`.
  Both levels are in the name because the curve is defined by the pair; scale is
  in the name so taste variants coexist.
- **Output layout is the wrapper's business, never the generator's.**
  `loudness-filters.py` and `check.py` write to the paths they are handed, and
  their CLIs hand themselves bare filenames — output lands in the working
  directory, three files side by side. They must not learn that `PEQ/`, `REW/`
  or `images/` exist, must not create directories, and must not emit a path
  that assumes one. `regenerate.py` is the wrapper that knows the layout and
  files each artifact where the repository wants it. This is a standing
  instruction from the owner, not an accident of history.
- **`PEQ/` holds the committed tables, `REW/` the CamillaDSP YAML**, for
  60–90 dB @ 83 dB reference — the same ladder in two formats, which
  `test_every_committed_table_has_its_yaml` enforces. The split exists because
  the two are read differently: a `.md` renders as a page in the GitLab/GitHub
  file browser and gets typed in by hand, a `.yml` is loaded and never read.
  **60 dB is the floor**, not 62: at 59 dB the fitted cascade needs 12.35 dB
  and `check_budget` refuses it. `.gitignore` anchors `/filter_*` to the repo
  root, so root-level output is scratch while `PEQ/*.md`, `REW/*.yml` and
  `images/*.png` stay tracked.
- **Every committed table embeds its response plot** as
  `![...](../images/<stem>.png)`, written by `write_markdown_table`'s `image`
  argument — the link text comes from the caller, so the relative hop out of
  `PEQ/` is `regenerate.py`'s knowledge and not the generator's. The plot is a
  confirmation aid: hosts draw a curve while filters are entered, and a
  listener can compare shapes. A `---` rule separates it from the table:
  Markdown collapses blank lines, so the gap has to be a block of its own, and
  the blank line *before* the rule is load-bearing too — without it the line
  above becomes a setext heading. Two consequences: every preset now needs a
  response plot in `images/`, not just `FEATURED` (which now selects only the
  extra *error* plots the README quotes), and the image line sits in the file
  `check.py` parses — it is not a table row, and
  `test_embedded_plot_does_not_disturb_the_table` keeps it that way.
- **The floor and the suggested `--level` disagree by 2 dB, deliberately.**
  `suggest_alternatives` estimates from the peak of the *target* rather than
  from a fit it has not run, so it says 62 where 60 in fact fits. Do not
  "correct" it to 60: the conservatism is what makes every suggestion it emits
  one that actually works, which `test_suggestions_actually_fit_the_budget`
  asserts. The gap is documented in the README instead.

  This gap is also *how* "62 dB is the floor" became documentation. The ladder
  comment in `regenerate.py` was written in `f553cae`, after
  `suggest_alternatives` landed in `3660d1b`, and restated that function's
  output as an empirical fact — nobody ever fitted 61 or 60. The generator's
  advice is conservative by design; do not promote it to a measurement. When a
  limit matters, fit it and look at the result.
- **60 and 61 dB are the loosest presets in the set** — 0.2083 and 0.1755 dB
  residual against 0.0925 at 62 dB, with the low shelf pinned exactly to the
  12 dB cap. They ship because they fit, but they are not representative; from
  65 dB up the residual is under 0.06 dB. If a future change makes the deep end
  cheaper, recheck whether 59 dB comes into range too.
- **One ladder covers every reference.** The compensation curve depends on
  `level - reference`, not on the two separately (≤0.125 dB across references
  72–85 dB). The README carries the equivalence table; do not generate a
  per-reference grid, it is redundant.
- **README.md quotes generated numbers** (headroom, residual errors, filter
  tables). Regenerate the presets and update the README together.
- **The three docs have different audiences; keep them separate.**
  `README.md` is for listeners and for people interested in the theory — using
  the presets, measuring `--level`, the maths, the relationship to the standard.
  `CONTRIBUTING.md` is for anyone cloning the repo — obtaining the ISO data,
  running the suite, the pylint bar. `CLAUDE.md` is the working notes.
  Setup mechanics (`cp ... .example`, `pytest`, `pylint`) belong in
  `CONTRIBUTING.md`, not the README; a claim about *what was verified* belongs
  in the README, with the how-to linked. Do not restate one in the other —
  cross-link.

## Domain facts worth knowing before changing the math

- `--level` is *measured* (broadband, C-weighted, slow). `--reference` is a
  property of the *recording*. They are not interchangeable.
- A measurement-convention offset shared by both cancels to first order
  (<0.05 dB); a 6 dB error in `--level` alone costs ~3.15 dB. Optimize for
  repeatability of the measurement, not for fit precision.
- **Five bands exhaust the ISO target; do not add a second tier back.** The
  removed refinement bands came out at 0.01–0.03 dB, and across the whole
  committed ladder they changed the response by *less than the rounding applied
  to publish them* — at 0.1 dB gain entry the ten-band set was numerically
  identical to the five-band set in ten of eleven presets, and the one exception
  was a rounding accident (two bands at exactly ±0.05). The 83→75 preset
  improved by 0.0001 dB for five extra filter entries, with four of its five
  refinement bands pinned at `MIN_Q` — the optimizer parking bands against a
  constraint because there was no residual left to work on.
- **Band count is not the lever people expect.** With adequate multistart, a
  jointly-fitted 8-band set beats 5 bands by 0.0046 dB raw — well under the
  0.014–0.017 dB the publication rounding costs, so it is invisible in the
  artifact. Search quality dominates: at 83→74 dB, going from 4 to 20 restarts
  improved the published error by 41% (0.0654 → 0.0384 dB). But that is
  level-dependent — 83→62 dB lands in the same basin on every restart, so
  multistart buys it nothing and its ~0.09 dB is a structural limit.
- **Roon renders more coarsely than it stores.** Its collapsed filter list shows
  integer Hz, 0.1 dB and 0.01 Q, but entering 100.4 Hz versus 100.0 Hz produces
  a visibly different response curve, so the full float survives. Publication
  precision is therefore chosen from what changes the response, not from what
  the UI echoes back. The preamp/headroom field is the genuine exception at
  `%.1f`.
