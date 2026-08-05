# Developing on this project

Everything here is for people cloning or forking the repository. If you only
want to *use* the filters, you need none of it — the tables in [PEQ](PEQ) are
ready to type in and the YAML in [REW](REW) is ready to load, and
[README.md](README.md) explains how. Nothing below is required to listen to
music.

---

## Before anything will run

### 1. Python dependencies

```bash
pip install -r requirements.txt
```

### 2. ISO 226:2023 Table 1 — **required**

**You need a copy of the standard.** This is the part that surprises people, so
it is first.

Table 1 holds the 29 per-frequency coefficients — $\alpha_f$, $L_U$ and $T_f$ —
that ISO 226 Formula (1) is evaluated from. They belong to ISO. Permission to
redistribute them was requested and has not been granted, so **they are not in
this repository**, and without them nothing computes: no import, no test
collection, no generator.

```bash
cp tests/iso226_table1.py.example reference/iso226_table1.py
# then fill in the three columns from your own copy of the standard
```

Buy it at <https://www.iso.org/standard/83117.html>. The template explains the
ordering; `reference/` is gitignored.

Use the **third edition**. ISO 226:2003 is not interchangeable — every
$\alpha_f$ changed when the loudness exponent at 1 kHz was revised from 0.25 to
0.30, several $L_U$ values moved by 0.1 dB, and Formula (1) itself changed.

Without the file you get:

```
ImportError: ISO 226:2023 Table 1 coefficients not found.
Expected: .../reference/iso226_table1.py
```

The loader checks the column lengths and that $L_U$ is exactly 0.0 at 1 kHz —
true by definition, since $L_U$ is specified *relative to* 1 kHz. That catches
an off-by-one during transcription, which is both the likeliest mistake and
otherwise completely symptomless: it would shift every contour by one
third-octave and still look plausible.

### 3. ISO 226:2023 Annex B — optional, but it is the best test here

Annex B, Table B.1 publishes the contours themselves. Supplying the 40 phon row
enables `test_matches_published_annex_b`, the only assertion in the project
whose expected values come from outside the project.

```bash
cp tests/annex_b_reference.py.example reference/annex_b_2023.py
# then type in the 40 phon row — 29 values, 20 Hz to 12.5 kHz
```

Without it that one test skips and everything else still runs.

### Never commit either file

`reference/` is gitignored as a directory. Do not add exceptions to that, and do
not "helpfully" paste values found in a paper, a Wikipedia table, a MATLAB File
Exchange entry or another GitHub repository. Those are no more licensed than
ISO's own copy, and provenance is the entire point. See [NOTICE](NOTICE).

---

## Running things

```bash
# Generate filter_<ref>_to_<level>_s<scale>.{md,yml,png} in the working
# directory — the generator never writes into a project subdirectory
python loudness-filters.py --level <db> [--reference <db>] [--scale <0.1-1.0>]

# Check published values against the ideal target; writes an error plot
python check.py --level <db> [--reference <db>] [--scale <s>]

# Rebuild every committed preset and figure (~5.5 minutes)
python regenerate.py
python regenerate.py --list          # what would be built, without building it
```

`regenerate.py` is the single source of truth for which presets ship — the
`LADDER`, `EXTRA` and `FEATURED` lists in that file, not the contents of
`PEQ/` or `REW/`.
Run it after any change to the math, the optimizer or the coefficients, then
reconcile the README, which quotes headroom values, residual errors and filter
tables.

It is also the only thing that knows the repository layout: the generator
writes to the working directory, and `regenerate.py` places each preset's
table in `PEQ/`, its CamillaDSP config in `REW/` and its plots in `images/`,
and links the table to its plot. Do not teach the generator about those
directories — a wrapper that arranges output is easier to keep honest than a
tool that assumes where it is being run.

A single generator run takes 20–45 seconds. It is data-dependent: the search
stops when it reaches its target, when it stops improving, or at a restart cap,
so a hard level like 62 dB costs about twice an easy one.

---

## Tests

```bash
python -m pytest tests/                  # all 124 (~30 s)
python -m pytest tests/ -m "not slow"    # 113 fast ones (~1 s)
```

The `slow` ones generate a real preset and assert what actually ships: that no
band exceeds the host's ±12 dB limit, that adjacent bands stay far enough apart,
that the total gain budget holds, that the search returns values already at
publication precision, that the extrapolation outside the ISO range stays
bounded, and — the one that matters most — that the published headroom figure
keeps the response at or below 0 dBFS at every verified sample rate.

They share one session-scoped `preset` fixture that runs the optimizer once. Add
new integration assertions to that fixture rather than generating another
preset.

### Why the suite anchors on things the project does not compute

`check.py` computes its ideal target with the same `iso226_spl` used to design
the filters, and evaluates them with the same `get_filter_response` used to fit
them. It therefore cannot detect an error in either routine — only that rounding
and parsing are faithful. **A low residual error from `check.py` is not evidence
that the math is right.**

So two groups of tests deliberately reach outside that circle:

* `test_matches_published_annex_b` — Formula (1) against ISO's own published
  contours. Ships disabled; see above.
* `test_high_shelf_passband_is_flat_at_every_rate` and
  `test_shelves_never_overshoot_their_own_gain` — the biquads against properties
  a shelving filter must have by definition: a cut may never produce a boost,
  and a high shelf must be 0 dB well below its corner.

That second group earned its place. It caught a sign error in the `b2`
coefficient of the high-shelf formula that had shipped since the project's first
version. The faulty term scaled with $\cos(\omega_0)$, so it was nearly
invisible at the sample rate and corner frequency most often used and grew from
there — in the then-current 65 dB preset, a **0.467 dB passband offset at
44.1 kHz, 1.46 dB at 14.2 kHz and 6.25 dB at 96 kHz**, while `check.py`
cheerfully reported 0.1185 dB because it was measuring the filters with the same
broken function that had built them.

---

## Code quality

**pylint must reach 10.00/10.**

```bash
python -m pylint check.py loudness-filters.py iso226_utils.py regenerate.py tests/
```

Run it exactly like that. Linting `tests/` on its own reports spurious
`import-error`, because the repo root only lands on `sys.path` when the modules
are linted together.

Treat every finding as a real defect until shown otherwise — on this project
they repeatedly have been. A lint pass once found `check.py` calling
`sys.path.insert` *after* the import it existed to enable, which worked only
because Python happens to put a script's own directory on the path. More
recently, a cluster of `R0913`/`R0914` findings that had been parked for a long
time turned out to be pointing at a real design problem, and were cleared by
bundling `(level, reference, scale)` into the `Compensation` type rather than by
silencing them.

The single exception is a fix that would genuinely harm clarity. When that
applies, disable the check **at the site** with a comment saying why — never in
a config file, and never a bare `# pylint: disable=` with no reasoning. Prefer
restructuring over suppressing.

Any Bash added to the repository must pass `shellcheck -S style` cleanly. There
is essentially no excuse for a finding at that level.

---

## Architecture

[CLAUDE.md](CLAUDE.md) carries the working notes: what each module does, the
invariants that must not be broken, and the domain facts worth knowing before
changing the math. It is written for an AI coding assistant, but it is the most
complete description of the design and is worth reading first.

Two things there that most often catch people out:

* **Everything normalizes to 0 dB at 1 kHz.** `ISO_FREQ`, `ISO_AF`, `ISO_LU` and
  `ISO_TF` are positionally aligned to ISO 226:2023 Table 1 — do not reorder
  them.
* **Filter type strings** (`'Peak'`, `'Low Shelf'`, `'High Shelf'`) are matched
  literally in `get_biquad_coefs`, written into Markdown cells that `check.py`
  parses back, and mapped in the YAML writer. Changing one requires all three.
