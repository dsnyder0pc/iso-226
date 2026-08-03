#!/usr/bin/env python
"""
Regenerate every committed preset and figure.

Run this after any change to the filter math, the optimizer or the ISO
coefficients. It is the single source of truth for which presets ship: the
ladder below is the definition, not the contents of REW/.

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

# 3 dB steps across the usable range. 62 dB is the floor: below it the
# correction needs more than the 12 dB a host PEQ can apply. 89 dB is three
# steps above the reference, past which the correction is a slight cut.
#
# A listener whose measured level falls between two rungs snaps to the nearer
# one and loses at most ~0.8 dB, which sits inside the uncertainty of their own
# SPL measurement. Because the correction depends on (level - reference) rather
# than on either level alone, these same files serve every mastering reference
# from 72 to 85 dB -- see the equivalence table in the README.
LADDER = [62, 65, 68, 71, 74, 77, 80, 83, 86, 89]

# Not on the 3 dB grid, but they are the levels the README and the article use
# as illustrations, so they ship too rather than leaving those examples
# undownloadable.
EXTRA = [75, 85]

# These additionally get a response plot and an error plot in images/.
FEATURED = [65, 75, 85]

REW_DIR = os.path.join(HERE, "REW")
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


def generate(level, with_figures):
    """Build one preset, install it in REW/, and optionally plot it."""
    comp = Compensation(float(level), REFERENCE, SCALE)
    stem = lf.preset_stem(comp)
    started = time.perf_counter()

    result = _quiet(lf.calculate_filters, comp)
    lf.check_budget(result, comp)
    headroom = lf.headroom_adjustment(result)

    _quiet(lf.write_markdown_table, result, comp, headroom,
           os.path.join(REW_DIR, f"{stem}.md"))
    _quiet(lf.write_camilladsp_yaml, result, comp, headroom,
           os.path.join(REW_DIR, f"{stem}.yml"))

    if with_figures:
        _quiet(lf.plot_frequency_response, result, comp, headroom,
               os.path.join(IMAGES_DIR, f"{stem}.png"))
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

    levels = sorted(set(LADDER) | set(EXTRA))
    if args.list:
        print(f"reference {REFERENCE:g} dB, scale {SCALE:g}\n")
        for level in levels:
            marks = []
            if level in LADDER:
                marks.append("ladder")
            if level in EXTRA:
                marks.append("extra")
            if level in FEATURED:
                marks.append("figures")
            print(f"  {level:3d} dB  ({level - REFERENCE:+3.0f} dB relative)"
                  f"  {', '.join(marks)}")
        print(f"\n{len(levels)} presets -> {2 * len(levels)} files in REW/, "
              f"{2 * len(FEATURED)} in images/")
        return 0

    os.makedirs(REW_DIR, exist_ok=True)
    os.makedirs(IMAGES_DIR, exist_ok=True)
    for directory, suffixes in ((REW_DIR, (".yml", ".md")),
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
    print(f"  REW/    {2 * len(levels)} files")
    print(f"  images/ {2 * len(FEATURED)} files")
    print("\nThe README quotes headroom values, residual errors and filter "
          "tables.\nCheck them against the output above before committing.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
