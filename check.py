#!/usr/bin/env python
"""
Verification script for equal-loudness PEQ filter profiles.

Calculates the residual deviation error between standard ISO 226 target curves
and the frequency response of generated PEQ filters for a given average playback level.
"""

import argparse
import os
import sys
import subprocess
import numpy as np
import matplotlib.pyplot as plt
from iso226_utils import ISO_FREQ, iso226_spl, get_filter_response


def parse_markdown_filters(filepath):
    """Parses PEQ filters from a generated Markdown table file.

    Args:
        filepath (str): Path to the Markdown table file.

    Returns:
        list: List of filter parameter tuples (ftype, fc, gain, q).
    """
    filters = []
    if not os.path.exists(filepath):
        return filters

    with open(filepath, 'r', encoding='utf-8') as file:
        for line in file:
            line_strip = line.strip()
            if not line_strip.startswith('|'):
                continue
            parts = [p.strip() for p in line_strip.split('|')]
            if len(parts) < 7:
                continue
            if parts[1] == 'Band' or parts[1].startswith(':---'):
                continue
            try:
                ftype = parts[2]
                fc = float(parts[3])
                gain = float(parts[4])
                q_val = float(parts[5])
                filters.append((ftype, fc, gain, q_val))
            except ValueError:
                continue
    return filters


def parse_markdown_reference_level(filepath):
    """Parses the reference level from a generated Markdown table file if present.

    Defaults to 83.0 if not found or file doesn't exist.
    """
    if not os.path.exists(filepath):
        return 83.0
    with open(filepath, 'r', encoding='utf-8') as file:
        for line in file:
            if "Reference Level:" in line:
                try:
                    parts = line.split("Reference Level:")
                    if len(parts) > 1:
                        ref_part = parts[1].split("dB")[0].strip()
                        return float(ref_part)
                except ValueError:
                    pass
    return 83.0


def ensure_filter_file(level, md_filename, requested_reference):
    """Ensures the filter Markdown file exists and matches the requested reference level.

    Returns the actual reference level of the file.
    """
    file_ref_level = None
    if os.path.exists(md_filename):
        file_ref_level = parse_markdown_reference_level(md_filename)

    ref_level = requested_reference
    if ref_level is None:
        ref_level = file_ref_level if file_ref_level is not None else 83.0

    # Regenerate if file doesn't exist or reference level doesn't match
    need_regeneration = not os.path.exists(md_filename)
    if (not need_regeneration and requested_reference is not None
            and file_ref_level != requested_reference):
        print(
            f"Existing file '{md_filename}' has reference level "
            f"{file_ref_level} dB, but {requested_reference} dB was requested. "
            "Regenerating..."
        )
        need_regeneration = True

    if need_regeneration:
        print("Generating filters using loudness-filters.py...")
        script_dir = os.path.dirname(os.path.abspath(__file__))
        filters_script = os.path.join(script_dir, 'loudness-filters.py')
        subprocess.run([
            sys.executable, filters_script,
            '--level', str(level),
            '--reference', str(ref_level)
        ], check=True)
    return ref_level


def plot_residual_error(error, level, ref_level, max_error, plot_filename):
    """Plots the residual error of the filters and saves to PNG."""
    level_str = f"{int(level)}" if level.is_integer() else f"{level}"
    ref_str = f"{int(ref_level)}" if ref_level.is_integer() else f"{ref_level}"

    plt.figure(figsize=(12, 6))
    plt.semilogx(
        ISO_FREQ, error, 'o-',
        label=f'{level_str} dB Target Residual Error',
        color='#e377c2', linewidth=2
    )
    plt.axhline(0, color='black', linestyle='--', alpha=0.7)
    title_str = (
        'PEQ Filter Error Matrix Relative to Standard ISO 226 Contours\n'
        f'({level_str} dB referenced to {ref_str} dB)'
    )
    title_str += f'\n(Maximum Residual Error: {max_error:.4f} dB)'
    plt.title(title_str)
    plt.xlabel('Frequency (Hz)')
    plt.ylabel('Deviation Error (dB)')
    plt.grid(True, which='both', linestyle='--', alpha=0.5)
    plt.xlim([20, 12500])
    plt.ylim([-2.0, 2.0])
    plt.legend()
    plt.tight_layout()
    plt.savefig(plot_filename, dpi=150)
    plt.close()
    print(f"Verification complete. Error plot saved as '{plot_filename}'.")


def main():
    """Main execution function to parse arguments, run filter generation,

    compute residual error, and plot results.
    """
    parser = argparse.ArgumentParser(
        description='Verify Equal-Loudness PEQ filter residual error.'
    )
    parser.add_argument('--level', type=float, default=65.0,
                        help='Target average playback level in dB (default: 65.0)')
    parser.add_argument('--reference', type=float, default=None,
                        help='Reference level for flat playback in dB (default: read from file, or 83.0)')
    args = parser.parse_args()

    # Determine filenames based on level
    level_str = f"{int(args.level)}" if args.level.is_integer() else f"{args.level}"
    md_filename = f"filter-{level_str}db.md"
    plot_filename = f"iso_226_filter_error_for_{level_str}db.png"

    # Ensure filter file exists and matches reference level
    ref_level = ensure_filter_file(args.level, md_filename, args.reference)

    # Read the PEQ filters from the Markdown table file
    filters = parse_markdown_filters(md_filename)

    # Calculate Ideal Target
    ref_spl = iso226_spl(ref_level)
    target_spl = iso226_spl(args.level)

    # Delta curve normalized at 1000 Hz (index 17 in standard preferred frequencies)
    ideal_delta = (target_spl - target_spl[17]) - (ref_spl - ref_spl[17])

    # Calculate Filter response at exact standard check points
    resp = get_filter_response(filters, ISO_FREQ)
    error = resp - ideal_delta

    # Calculate max residual error
    max_error = np.max(np.abs(error))
    print(f"Max residual error: {max_error:.4f} dB")

    # Generate and save the verification error plot
    plot_residual_error(error, args.level, ref_level, max_error, plot_filename)


if __name__ == "__main__":
    main()
