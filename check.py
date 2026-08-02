#!/usr/bin/env python
"""
Verification tool for equal-loudness compensation PEQ filter sets.

Reads the published (rounded) filter values back out of the generated Markdown
table and compares their response against the ideal ISO 226 target, plotting the
residual error for the essential five bands and for all ten so a listener can
see what the optional bands actually buy.
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

from iso226_utils import DESIGN_FS, ISO_FREQ, get_filter_response, ideal_delta

_spec = importlib.util.spec_from_file_location(
    "_lf", os.path.join(HERE, "loudness-filters.py"))
_lf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_lf)
preset_stem = _lf.preset_stem

ESSENTIAL_BANDS = 5
DEFAULT_REFERENCE = 83.0
DEFAULT_SCALE = 1.0

# Below this the optional bands are indistinguishable from fitting noise. For
# scale, Roon accepts gains to 0.1 dB and listeners in the published listening
# tests repeat their own judgements only to within several dB.
NEGLIGIBLE_IMPROVEMENT_DB = 0.02


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


def ensure_filter_file(level, ref, scale, md_filename):
    """Generate the filter table if it is not already present.

    The filename now encodes the reference and scale, so there is no ambiguity
    to resolve: a missing file simply means that combination has not been
    generated yet.
    """
    if os.path.exists(md_filename):
        recorded_ref, recorded_scale = parse_markdown_metadata(md_filename)
        if recorded_ref != ref or recorded_scale != scale:
            print(f"Warning: '{md_filename}' records reference "
                  f"{recorded_ref} dB / scale {recorded_scale}, but its name "
                  f"says {ref} dB / {scale}. Regenerating.")
        else:
            return

    print(f"Generating {md_filename} using loudness-filters.py...")
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          'loudness-filters.py')
    subprocess.run([sys.executable, script, '--level', str(level),
                    '--reference', str(ref), '--scale', str(scale)], check=True)


def plot_residual_error(err_essential, err_all, level, ref, scale, filename):
    """Plot residual error for the essential five bands and for all ten."""
    max_essential = float(np.max(np.abs(err_essential)))
    max_all = float(np.max(np.abs(err_all)))

    plt.figure(figsize=(12, 6))
    plt.fill_between(ISO_FREQ, err_essential, err_all,
                     color='#9467bd', alpha=0.18,
                     label='Difference made by bands 6–10')
    plt.semilogx(ISO_FREQ, err_essential, 'o--', color='#ff7f0e', linewidth=1.8,
                 markersize=4, label=f'Essential 5 bands (max {max_essential:.4f} dB)')
    plt.semilogx(ISO_FREQ, err_all, 'o-', color='#1f77b4', linewidth=2,
                 markersize=4, label=f'All 10 bands (max {max_all:.4f} dB)')
    plt.axhline(0, color='black', linestyle='--', alpha=0.7)

    level_str = f"{int(level)}" if float(level).is_integer() else f"{level}"
    title = ('Residual Error Relative to the Ideal ISO 226 Target\n'
             f'listening at {level_str} dB, mastered for {ref:g} dB'
             + (' (default)' if ref == DEFAULT_REFERENCE else '')
             + (f', scale {scale:.2f}' if scale != 1.0 else '')
             + f' · evaluated at {DESIGN_FS / 1000:.1f} kHz')
    plt.title(title)
    plt.xlabel('Frequency (Hz)')
    plt.ylabel('Deviation Error (dB)')
    plt.grid(True, which='both', linestyle='--', alpha=0.5)
    plt.xlim([20, 12500])
    span = max(max_essential, max_all, 0.05) * 1.6
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

    ref, scale = args.reference, args.scale
    stem = preset_stem(args.level, ref, scale)
    md_filename = f"{stem}.md"
    plot_filename = f"{stem}_error.png"

    try:
        ensure_filter_file(args.level, ref, scale, md_filename)
    except subprocess.CalledProcessError:
        return 1

    filters = parse_markdown_filters(md_filename)
    if not filters and ref == args.level:
        # The generator writes prose instead of a table when the listening level
        # equals the mastering reference: the ideal correction is identically
        # zero, so there is nothing to fit and nothing to verify.
        print(f"Listening level equals the mastering reference ({ref:g} dB), so "
              "the ideal correction is 0.00 dB at every frequency.")
        print("No filters to verify.")
        return 0
    if len(filters) < ESSENTIAL_BANDS:
        print(f"Error: '{md_filename}' contains only {len(filters)} filter rows.",
              file=sys.stderr)
        return 1

    target = ideal_delta(args.level, ref, scale)
    err_essential = get_filter_response(filters[:ESSENTIAL_BANDS], ISO_FREQ) - target
    err_all = get_filter_response(filters, ISO_FREQ) - target

    max_essential = float(np.max(np.abs(err_essential)))
    max_all = float(np.max(np.abs(err_all)))
    delta = max_essential - max_all
    print(f"Max residual error, essential 5 bands: {max_essential:.4f} dB")
    print(f"Max residual error, all 10 bands:      {max_all:.4f} dB")
    print(f"Change from adding bands 6-10:         {delta:+.4f} dB")
    if abs(delta) < NEGLIGIBLE_IMPROVEMENT_DB:
        print("  -> within fitting noise. Five bands have already tracked the "
              "target as closely as this topology can;")
        print("     entering bands 6-10 by hand is not worth the effort.")

    plot_residual_error(err_essential, err_all, args.level, ref, scale,
                        plot_filename)
    return 0


if __name__ == "__main__":
    sys.exit(main())
