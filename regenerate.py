#!/usr/bin/env python
"""
Regenerate every committed preset and figure.

Run this after any change to the filter math, the optimizer or the ISO
coefficients. It is the single source of truth for which presets ship: the
ladder below is the definition, not the contents of PEQ/ or REW/.

    python regenerate.py            # regenerate everything (several minutes)
    python regenerate.py --list     # show what would be generated, and exit

Expect roughly half a minute per preset, so the full set takes a few minutes.
The exact time depends heavily on the machine; the script reports each one as
it completes so a slow host looks slow rather than broken.
"""

import argparse
import contextlib
import importlib.util
import io
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# sys.path must be set up before the project modules can be imported.
# pylint: disable=wrong-import-position
from iso226_utils import (  # noqa: E402
    ISO_FREQ, Compensation, get_filter_response, ideal_delta,
)


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


lf = _load("loudness_filters", "loudness-filters.py")
checker = _load("checker", "check.py")

# --- What ships -------------------------------------------------------------
REFERENCE = 83.0        # the Katz monitoring convention; see the README
SCALE = 1.0             # full theoretical correction

# The rungs are the levels people actually choose, not an arithmetic grid. An
# even 3 dB series is tidy to generate and slightly wrong to use: it spends
# steps where nobody sits and skips the round numbers they reach for. So the
# spacing is 1 dB at the floor, where the correction moves fastest and the fit
# is tightest, and 2-3 dB through the range anyone listens in, landing on the
# values a listener is likely to have measured. 89 dB is the top, past which
# the correction is a slight cut anyway.
#
# No gap exceeds 3 dB, so snapping to the nearer rung still costs at most
# 0.79 dB of correction -- measured across the whole ladder, not assumed, and
# inside the uncertainty of the listener's own SPL reading. Because the
# correction depends on (level - reference) rather than on either level alone,
# these same files serve every mastering reference from 72 to 85 dB -- see the
# equivalence table in the README.
#
# 60 dB is the floor, not 62: at 59 dB the fitted cascade needs 12.35 dB and is
# refused. The generator's own --level suggestion still says 62, because
# suggest_alternatives estimates from the peak of the *target* rather than from
# a fit it has not run -- deliberately conservative, so that a suggestion it
# makes is always one that works. 60 and 61 are the levels where those two
# measures disagree, and they ship because they do fit.
#
# They are the loosest presets in the set: 0.21 and 0.18 dB residual against
# 0.09 at 62 dB, with the low shelf pinned to the 12 dB cap. Still well below
# audibility, but do not read them as typical.
#
# 83 dB is the reference itself. It carries no filters and says so; it ships
# because a listener already at their reference level who reaches for the
# nearest rung instead applies about 1.6 dB of correction they do not want.
LADDER = [60, 61, 62, 65, 68, 70, 72, 75, 78, 80, 83, 85, 87, 89]

# These additionally get an error plot in images/, because the README quotes
# them as worked examples. Every preset gets a response plot regardless: the
# PEQ/ pages embed it.
FEATURED = [65, 75, 85]

PEQ_DIR = os.path.join(HERE, "PEQ")      # the tables, read as rendered pages
REW_DIR = os.path.join(HERE, "REW")      # CamillaDSP YAML, loaded not read
IMAGES_DIR = os.path.join(HERE, "images")


def _quiet(func, *args, **kwargs):
    """Call func with its own output swallowed.

    The writers print their tables to stdout and the generator reports fit
    progress to stderr. Both are useful for a single CLI run and both would
    shred the one-line-per-preset status this script prints, so each call is
    silenced and the interesting figures are re-reported from the result.
    """
    with contextlib.redirect_stdout(io.StringIO()), \
            contextlib.redirect_stderr(io.StringIO()):
        return func(*args, **kwargs)


def generate(level, with_error_plot):
    """Build one preset: table in PEQ/, YAML in REW/, response plot in images/."""
    comp = Compensation(float(level), REFERENCE, SCALE)
    stem = lf.preset_stem(comp)
    started = time.perf_counter()

    result = _quiet(lf.calculate_filters, comp)
    lf.check_budget(result, comp)
    headroom = lf.headroom_adjustment(result)

    # The table and its plot live in different directories, so the page links
    # across. Relative, because GitLab and GitHub both render it from the blob
    # view and a repo-absolute path would only work on one of them.
    _quiet(lf.write_markdown_table, result, comp, headroom,
           os.path.join(PEQ_DIR, f"{stem}.md"), f"../images/{stem}.png")
    _quiet(lf.write_camilladsp_yaml, result, comp, headroom,
           os.path.join(REW_DIR, f"{stem}.yml"))
    _quiet(lf.plot_frequency_response, result, comp, headroom,
           os.path.join(IMAGES_DIR, f"{stem}.png"))

    if with_error_plot:
        _quiet(checker.plot_residual_error,
               get_filter_response(result["filters"], ISO_FREQ)
               - ideal_delta(comp),
               comp, os.path.join(IMAGES_DIR, f"{stem}_error.png"))

    elapsed = time.perf_counter() - started
    return headroom, result, elapsed


def main():
    """Regenerate every preset, or list what would be generated."""
    parser = argparse.ArgumentParser(
        description="Regenerate every committed preset and figure.")
    parser.add_argument("--list", action="store_true",
                        help="show what would be generated, then exit")
    args = parser.parse_args()

    levels = sorted(LADDER)
    if args.list:
        print(f"reference {REFERENCE:g} dB, scale {SCALE:g}\n")
        for level in levels:
            marks = ["ladder"]
            if level in FEATURED:
                marks.append("error plot")
            print(f"  {level:3d} dB  ({level - REFERENCE:+3.0f} dB relative)"
                  f"  {', '.join(marks)}")
        print(f"\n{len(levels)} presets -> {len(levels)} tables in PEQ/, "
              f"{len(levels)} configs in REW/, "
              f"{len(levels) + len(FEATURED)} figures in images/")
        return 0

    for directory in (PEQ_DIR, REW_DIR, IMAGES_DIR):
        os.makedirs(directory, exist_ok=True)
    for directory, suffixes in ((PEQ_DIR, (".md",)),
                                (REW_DIR, (".yml",)),
                                (IMAGES_DIR, (".png",))):
        for name in os.listdir(directory):
            if name.startswith("filter_") and name.endswith(suffixes):
                os.remove(os.path.join(directory, name))

    print(f"Regenerating {len(levels)} presets at reference {REFERENCE:g} dB, "
          f"scale {SCALE:g}.")
    print("Half a minute or so each, depending on the machine.\n")

    total, missed = 0.0, False
    for index, level in enumerate(levels, 1):
        label = f"[{index}/{len(levels)}] {REFERENCE:g} -> {level} dB"
        print(f"  {label:<28}", end=" ", flush=True)
        headroom, result, elapsed = generate(level, level in FEATURED)
        total += elapsed
        missed = missed or not result['target_met']
        print(f"headroom {headroom:+5.1f} dB   "
              f"err {result['error']:.4f} dB"
              f"{' ' if result['target_met'] else '*'}  "
              f"{result['restarts']:2d} restarts   "
              f"({elapsed:4.1f} s)")

    if missed:
        print(f"\n  * did not reach the {lf.PUBLISHED_ERROR_TARGET_DB:g} dB "
              f"target. That is the honest limit of {lf.BAND_COUNT} bands at "
              "those levels, not a failure;\n    the residual is still far "
              "below audibility.")

    print(f"\nDone in {total / 60:.1f} minutes.")
    print(f"  PEQ/    {len(levels)} tables")
    print(f"  REW/    {len(levels)} configs")
    print(f"  images/ {len(levels) + len(FEATURED)} figures")
    print("\nThe README quotes headroom values, residual errors and filter "
          "tables.\nCheck them against the output above before committing.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
