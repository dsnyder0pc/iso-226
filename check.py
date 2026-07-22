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


def main():
    """Main execution function to parse arguments, run filter generation,

    compute residual error, and plot results.
    """
    parser = argparse.ArgumentParser(
        description='Verify Equal-Loudness PEQ filter residual error.'
    )
    parser.add_argument('--level', type=float, default=65.0,
                        help='Target average playback level in dB (default: 65.0)')
    args = parser.parse_args()

    # Determine filenames based on level
    level_str = f"{int(args.level)}" if args.level.is_integer() else f"{args.level}"
    md_filename = f"filter-{level_str}db.md"
    plot_filename = f"iso_226_filter_error_for_{level_str}db.png"

    # Make system call to generate the filter file if it doesn't exist
    if not os.path.exists(md_filename):
        print(f"File '{md_filename}' not found. Generating filters using loudness-filters.py...")
        script_dir = os.path.dirname(os.path.abspath(__file__))
        filters_script = os.path.join(script_dir, 'loudness-filters.py')
        subprocess.run([sys.executable, filters_script, '--level', str(args.level)], check=True)

    # Read the PEQ filters from the Markdown table file
    filters = parse_markdown_filters(md_filename)

    # Calculate Ideal Target
    ref_spl = iso226_spl(83.0)
    target_spl = iso226_spl(args.level)

    # Delta curve normalized at 1000 Hz (index 17 in standard preferred frequencies)
    ideal_delta = (target_spl - target_spl[17]) - (ref_spl - ref_spl[17])

    # Calculate Filter response at exact standard check points
    resp = get_filter_response(filters, ISO_FREQ)
    error = resp - ideal_delta

    # Calculate max residual error
    max_error = np.max(np.abs(error))
    print(f"Max residual error: {max_error:.4f} dB")

    # Plot generation
    plt.figure(figsize=(12, 6))
    plt.semilogx(
        ISO_FREQ, error, 'o-',
        label=f'{level_str} dB Target Residual Error',
        color='#e377c2', linewidth=2
    )
    plt.axhline(0, color='black', linestyle='--', alpha=0.7)
    title_str = f'PEQ Filter Error Matrix Relative to Standard ISO 226 Contours ({level_str} dB)'
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


if __name__ == "__main__":
    main()
