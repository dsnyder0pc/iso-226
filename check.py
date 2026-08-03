#!/usr/bin/env python
"""
Verification tool for equal-loudness compensation PEQ filter sets.

Reads the published (rounded) filter values back out of the generated Markdown
table and compares their response against the ideal ISO 226 target, plotting the
residual error.

This is the only check that does not share code with the thing it checks: the
generator computes its published error from its own in-memory fit, whereas this
reads the numbers a listener would actually type and evaluates those.
"""

import argparse
import importlib.util
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# Two deliberate departures from import-at-the-top: the path setup above has to
# run first, and matplotlib's backend must be chosen before pyplot loads.
# pylint: disable=wrong-import-position
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from iso226_utils import (
    DEFAULT_REFERENCE, DEFAULT_SCALE, DESIGN_FS, ISO_FREQ, Compensation,
    get_filter_response, ideal_delta,
)

_spec = importlib.util.spec_from_file_location(
    "_lf", os.path.join(HERE, "loudness-filters.py"))
_lf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_lf)
preset_stem = _lf.preset_stem

# Imported rather than restated: the band count is part of the file format this
# module parses, so the two must not be able to drift apart.
BAND_COUNT = _lf.BAND_COUNT


def parse_markdown_filters(filepath):
    """Parse PEQ filter rows from a generated Markdown table, in band order."""
    filters = []
    if not os.path.exists(filepath):
        return filters
    with open(filepath, 'r', encoding='utf-8') as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped.startswith('|'):
                continue
            parts = [p.strip() for p in stripped.split('|')]
            if len(parts) < 7 or parts[1] == 'Band' or parts[1].startswith(':---'):
                continue
            try:
                filters.append((parts[2], float(parts[3]),
                                float(parts[4]), float(parts[5])))
            except ValueError:
                continue
    return filters


def parse_markdown_metadata(filepath):
    """Read the reference level and scale recorded in a generated table."""
    ref, scale = DEFAULT_REFERENCE, DEFAULT_SCALE
    if not os.path.exists(filepath):
        return ref, scale
    with open(filepath, 'r', encoding='utf-8') as handle:
        text = handle.read()
    match = re.search(r'[Mm]astering reference\s+([0-9.]+)\s*dB', text)
    if match:
        ref = float(match.group(1))
    match = re.search(r'scale\s+([0-9.]+)', text)
    if match:
        scale = float(match.group(1))
    return ref, scale


def ensure_filter_file(comp, md_filename):
    """Generate the filter table if it is not already present.

    The filename encodes the reference and scale, so there is no ambiguity to
    resolve: a missing file simply means that combination has not been
    generated yet.
    """
    if os.path.exists(md_filename):
        recorded_ref, recorded_scale = parse_markdown_metadata(md_filename)
        if recorded_ref != comp.reference or recorded_scale != comp.scale:
            print(f"Warning: '{md_filename}' records reference "
                  f"{recorded_ref} dB / scale {recorded_scale}, but its name "
                  f"says {comp.reference} dB / {comp.scale}. Regenerating.")
        else:
            return

    print(f"Generating {md_filename} using loudness-filters.py...")
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          'loudness-filters.py')
    subprocess.run([sys.executable, script, '--level', str(comp.level),
                    '--reference', str(comp.reference),
                    '--scale', str(comp.scale)], check=True)


def plot_residual_error(err, comp, filename):
    """Plot residual error for the published band set."""
    max_err = float(np.max(np.abs(err)))

    plt.figure(figsize=(12, 6))
    plt.semilogx(ISO_FREQ, err, 'o-', color='#1f77b4', linewidth=2,
                 markersize=4,
                 label=f'Published filter set (max {max_err:.4f} dB)')
    plt.axhline(0, color='black', linestyle='--', alpha=0.7)

    level_str = (f"{int(comp.level)}" if float(comp.level).is_integer()
                 else f"{comp.level}")
    title = ('Residual Error Relative to the Ideal ISO 226 Target\n'
             f'listening at {level_str} dB, mastered for {comp.reference:g} dB'
             + (' (default)' if comp.reference == DEFAULT_REFERENCE else '')
             + (f', scale {comp.scale:.2f}' if comp.scale != DEFAULT_SCALE else '')
             + f' · evaluated at {DESIGN_FS / 1000:.1f} kHz')
    plt.title(title)
    plt.xlabel('Frequency (Hz)')
    plt.ylabel('Deviation Error (dB)')
    plt.grid(True, which='both', linestyle='--', alpha=0.5)
    plt.xlim([20, 12500])
    span = max(max_err, 0.05) * 1.6
    plt.ylim([-span, span])
    plt.legend(loc='best')
    plt.tight_layout()
    plt.savefig(filename, dpi=150)
    plt.close()
    print(f"Error plot saved as '{filename}'.")


def main():
    """Verify a generated filter set and plot its residual error."""
    parser = argparse.ArgumentParser(
        description='Verify equal-loudness PEQ filter residual error.')
    parser.add_argument('--level', type=float, required=True,
                        help='Listening level in dB SPL (required, no default)')
    parser.add_argument('--reference', type=float, default=DEFAULT_REFERENCE,
                        help=f'Mastering reference level in dB SPL '
                             f'(default: {DEFAULT_REFERENCE:g})')
    parser.add_argument('--scale', type=float, default=DEFAULT_SCALE,
                        help=f'Fraction of the theoretical correction applied '
                             f'(default: {DEFAULT_SCALE:g})')
    args = parser.parse_args()

    try:
        comp = Compensation(args.level, args.reference, args.scale)
    except ValueError as err:
        print(f"Error: {err}", file=sys.stderr)
        return 1
    stem = preset_stem(comp)
    md_filename = f"{stem}.md"
    plot_filename = f"{stem}_error.png"

    try:
        ensure_filter_file(comp, md_filename)
    except subprocess.CalledProcessError:
        return 1

    filters = parse_markdown_filters(md_filename)
    if not filters and comp.is_null:
        # The generator writes prose instead of a table when the listening level
        # equals the mastering reference: the ideal correction is identically
        # zero, so there is nothing to fit and nothing to verify.
        print("Listening level equals the mastering reference "
              f"({comp.reference:g} dB), so "
              "the ideal correction is 0.00 dB at every frequency.")
        print("No filters to verify.")
        return 0
    if not filters:
        print(f"Error: '{md_filename}' contains no filter rows.", file=sys.stderr)
        return 1
    if len(filters) != BAND_COUNT:
        # Not fatal: verify whatever the file actually publishes. A mismatch
        # usually means the file predates a change to the band count.
        print(f"Warning: '{md_filename}' publishes {len(filters)} bands, but the "
              f"generator now produces {BAND_COUNT}. Verifying the file as it is.")

    target = ideal_delta(comp)
    err = get_filter_response(filters, ISO_FREQ) - target
    max_err = float(np.max(np.abs(err)))
    print(f"Max residual error, {len(filters)} bands as published: "
          f"{max_err:.4f} dB")

    plot_residual_error(err, comp, plot_filename)
    return 0


if __name__ == "__main__":
    sys.exit(main())
