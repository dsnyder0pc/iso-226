# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository does

Generates parametric EQ filter sets that compensate for the level-dependence of
human hearing, based on the **ISO 226:2023** equal-loudness contours (third
edition). Output is consumed by REW / CamillaDSP / Roon / miniDSP for real
listening rooms.

## Commands

```bash
pip install -r requirements.txt

# Generate filter_<ref>_to_<level>_s<scale>.{md,yml,png}
python loudness-filters.py --level <db> [--reference <db>] [--scale <0.1-1.0>]

# Verify published values against the ideal target; writes a dual-trace error plot
python check.py --level <db> [--reference <db>] [--scale <s>]

# Regression tests — run after touching any math
python -m pytest tests/                  # all 60 (~31 s)
python -m pytest tests/ -m "not slow"    # 52 fast ones (~2 s)

# Rebuild every committed preset and figure (several minutes)
python regenerate.py
python regenerate.py --list              # what would be generated, without doing it

# Linters — both must be clean before committing
python -m pylint check.py loudness-filters.py iso226_utils.py regenerate.py tests/
shellcheck -S style path/to/script.sh    # any Bash added to the repo
```

`regenerate.py` is the single source of truth for which presets ship — the
`LADDER`, `EXTRA` and `FEATURED` lists in that file, not the contents of `REW/`.
Run it after any change to the math, the optimizer or the coefficients, then
reconcile the README, which quotes headroom values, residual errors and filter
tables.

Tests marked `slow` share one session-scoped `preset` fixture that runs the
optimizer once (~30 s) and assert many shipped properties against it. Add new
integration assertions to that fixture rather than generating another preset.

A generator run takes ~30 s (constrained minimax with multistart). Batch
regeneration of the whole preset ladder takes several minutes — run it in the
background.

**Environment note:** the project uses a pyenv virtualenv named `iso-226`
(`.python-version`), which auto-activates only inside the project directory.
Running scripts from elsewhere gives `ModuleNotFoundError: No module named
'scipy'`. Use `/home/dsnyder/.pyenv/versions/iso-226/bin/python` explicitly, or
`cd` into the repo first.

## Architecture

- **`iso226_utils.py`** — all shared math.
  - `iso226_spl(phon, f_arr)`: ISO 226:2023 Formula (1). Coefficients
    interpolate in **log** frequency. Raises outside 20–90 phon, the range the
    standard defines.
  - `ideal_delta(level, ref, scale)`: the compensation target — difference of
    two contours, normalized to 0 dB at 1 kHz (`REF_1KHZ_INDEX`), times `scale`.
  - `build_target(...)`: returns `(grid, target, in_band_slice)`. The grid spans
    10 Hz–20 kHz; the target is **held flat** outside 20 Hz–12.5 kHz where ISO
    has no data. `in_band_slice` selects the ISO-backed region that the
    optimizer's objective actually minimizes over.
  - `get_biquad_coefs` / `get_filter_response`: RBJ Audio EQ Cookbook biquads,
    cascaded via `scipy.signal.freqz`. Default `fs` is `DESIGN_FS` = 44100.
  - `peak_gain(filters)`: worst peak across `VERIFY_RATES` (44.1/48/96/192 kHz).
  - `ANNEX_B_TOLERANCE_DB` = 0.05 — Table B.1 is printed to 0.1 dB, so this is
    exact agreement. The contour values themselves are ISO's and are **not** in
    the repo: they live in the gitignored `reference/annex_b_2023.py`, supplied
    from `tests/annex_b_reference.py.example` by whoever owns the standard.
    Without them `test_matches_published_annex_b` skips.

- **`loudness-filters.py`** — generator CLI.
  - `_fit_bands(...)`: minimax fit in **epigraph form** (minimize `t` subject to
    `|error| <= t`). Do not "simplify" this back to handing `np.max(np.abs(...))`
    to SLSQP — that function is non-differentiable at the optimum and fits 3–5×
    worse.
  - `calculate_filters(...)`: fits tier 1 (bands 1–5), rounds it, then fits
    tier 2 (bands 6–10) **on top of the frozen, rounded tier 1**, so the
    essential five are exactly the best standalone five-band solution.
  - `cascade_diagnostics(...)`: worst intermediate stage gain and quantization
    sensitivity. Guards against degenerate near-cancelling band pairs.
  - `check_budget(...)`: refuses over-budget requests with computed `--scale`
    and `--level` suggestions (estimated from the target's magnitude, not from
    the failed fit's peak).

- **`check.py`** — parses the **published, rounded** values back out of the
  Markdown table and plots residual error for bands 1–5 versus all 10. It
  imports `preset_stem` from the generator so both agree on filenames, and
  shells out to generate the preset if that file does not exist yet.

- **`tests/test_iso226.py`** — the math. `test_matches_published_annex_b` and
  the shelf-property tests are the ones that matter: they are the only checks
  not sharing code with the thing under test. The shelf tests caught a sign
  error in the RBJ high-shelf `b2` coefficient that had shipped since the first
  version and that `check.py` could never have detected.

- **`tests/test_generator.py`** — the generator plus the file formats that
  couple the two scripts. The Markdown/YAML round-trip tests are the ones most
  likely to earn their keep: `check.py` matches filter-type strings and table
  columns *positionally*, and nothing else notices when one side of that
  contract changes.

## Code quality bar

**pylint must reach 10.00/10.** Not "close enough" — the owner's standing
preference is a clean run. Treat every finding as a real defect until shown
otherwise, because on this project they repeatedly have been: a lint pass found
`check.py` calling `sys.path.insert` *after* the import it existed to enable,
which worked only because Python happens to put a script's own directory on the
path.

The single exception is a fix that would genuinely harm clarity or
maintainability. When that applies:

* disable the check **at the site**, with a comment saying why — never in a
  config file, and never a bare `# pylint: disable=` with no reasoning;
* prefer restructuring over suppressing. Four functions currently exceed the
  argument limit because `(level, reference, scale)` travels together through
  seven of them; the answer is a small frozen parameter object, not a disable
  comment.

Existing documented exceptions, all deliberate: `wrong-import-position` where
`sys.path` setup or matplotlib's backend selection must precede imports;
`import-outside-toplevel` for the lazy matplotlib import, which costs about a
second and is not needed by most invocations; `redefined-outer-name` in
`conftest.py`, where one pytest fixture requesting another necessarily shadows
the name.

**Known gap:** the score is 9.85. The remaining findings are all `R0913` /
`R0914` on the argument and local counts described above. They are left visible
on purpose — suppressing them would hide the refactor they are pointing at.
That refactor belongs with the Flask work, which needs the same validated
parameter bundle from query parameters.

**Any Bash added to this repo must pass `shellcheck -S style` cleanly.** There
is essentially no excuse for a finding at that level; fix the script rather than
silencing the check. (There are no shell scripts here at present — orchestration
lives in `regenerate.py` — so this applies to anything new.)

## Invariants — do not break these

- **Everything normalizes to 0 dB at 1 kHz** (`REF_1KHZ_INDEX = 17`). Don't
  reorder `ISO_FREQ` / `ISO_AF` / `ISO_LU` / `ISO_TF`; they are positionally
  aligned to ISO 226:2023 Table 1.
- **Filter type strings** (`'Peak'`, `'Low Shelf'`, `'High Shelf'`) are matched
  literally in `get_biquad_coefs`, written into Markdown cells that `check.py`
  parses back, and mapped in the YAML writer. Changing one requires all three.
- **Per-band gain is capped at ±12 dB** (Roon MUSE PEQ slider; miniDSP is ±16,
  so 12 satisfies both), plus a total-absolute-gain budget and non-overlapping
  per-tier frequency ranges. These exist to prevent degenerate solutions with
  two large opposing filters at nearly the same frequency — which measure fine
  end-to-end but overflow intermediate nodes in serial fixed-point DSPs and lose
  their cancellation under host coefficient quantization.
- **No filter band above 12 kHz.** A 16 kHz shelf extrapolates past the ISO data
  with no evidence behind it, and it is where the residual sample-rate
  dependence lives: the previous version's response at 20 kHz ranged from
  +8.44 dB at 44.1 kHz down to +6.32 dB at 192 kHz. (An earlier note here
  claimed a +12.73 dB peak at 192 kHz; that was an artifact of the high-shelf
  coefficient bug, not a real rate effect.)
- **Design and analyse at 44.1 kHz**, verify headroom across all `VERIFY_RATES`,
  and publish the worst case rounded *away from zero* to 0.1 dB (Roon's entry
  precision). One headroom number covers both the 5- and 10-band sets.
- **Out-of-band regions are constrained, not optimized.** Keep the target
  flat-held below 20 Hz and above 12.5 kHz with `EXTRAP_TOLERANCE_DB`; this is
  what keeps subsonic gain bounded.
- **Preset filenames encode the pair**: `filter_<ref>_to_<level>_s<scale>`,
  built by `preset_stem()` in `loudness-filters.py` and imported by `check.py`.
  Both levels are in the name because the curve is defined by the pair; scale is
  in the name so taste variants coexist.
- **`REW/` holds committed presets** for 62–90 dB @ 83 dB reference. 62 dB is
  the floor — below it the correction exceeds the 12 dB budget. `.gitignore`
  anchors `/filter_*` to the repo root, so root-level output is scratch while
  `REW/*.yml` and `images/*.png` stay tracked.
- **One ladder covers every reference.** The compensation curve depends on
  `level - reference`, not on the two separately (≤0.125 dB across references
  72–85 dB). The README carries the equivalence table; do not generate a
  per-reference grid, it is redundant.
- **README.md quotes generated numbers** (headroom, residual errors, filter
  tables). Regenerate the presets and update the README together.

## Domain facts worth knowing before changing the math

- `--level` is *measured* (broadband, C-weighted, slow). `--reference` is a
  property of the *recording*. They are not interchangeable.
- A measurement-convention offset shared by both cancels to first order
  (<0.05 dB); a 6 dB error in `--level` alone costs ~3.15 dB. Optimize for
  repeatability of the measurement, not for fit precision.
- The refinement bands (6–10) typically come out at 0.01–0.03 dB, below Roon's
  0.1 dB entry precision. This is expected — the ISO target is smooth enough
  that five bands exhaust it. The generator says so in the Markdown output when
  it is true; do not "fix" it by making tier 1 artificially worse.
