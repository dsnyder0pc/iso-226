#!/usr/bin/env python
"""
Loudness compensation filter generator.

Generates parametric EQ (PEQ) filters based on ISO 226 equal-loudness
contours relative to a reference level (83 dB), saves them to a Markdown
table file, and plots the combined frequency response to a PNG file.
"""

# pylint: disable=invalid-name

import argparse
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit
from iso226_utils import ISO_FREQ, iso226_spl, get_filter_response

# Standard reference level for flat playback
REF_LEVEL = 83.0

# Base EQ filter structure (frequencies and Q factors) used for curve fitting optimization
BASE_FILTERS = [
    ('Low Shelf', 35, 0.0, 0.71),
    ('Low Shelf', 75, 0.0, 0.71),
    ('Peak', 150, 0.0, 0.70),
    ('Peak', 300, 0.0, 1.00),
    ('Peak', 600, 0.0, 1.40),
    ('Peak', 1000, 0.0, 1.00),
    ('Peak', 3000, 0.0, 1.40),
    ('Peak', 6000, 0.0, 1.00),
    ('High Shelf', 10000, 0.0, 0.71),
    ('High Shelf', 16000, 0.0, 0.71),
]


def fit_model(freqs, *gains):
    """Model function for curve fitting. Calculates filter response for a given array of gains."""
    filters = []
    for i, (ftype, fc, _, q_val) in enumerate(BASE_FILTERS):
        filters.append((ftype, fc, gains[i], q_val))
    return get_filter_response(filters, freqs)


def calculate_filters_for_level(target_level):
    """Optimizes the EQ profile to fit the ISO 226 target delta curve at the requested target level."""
    # 1. Calculate the ideal delta curve
    ref_spl = iso226_spl(REF_LEVEL, ISO_FREQ)
    target_spl = iso226_spl(target_level, ISO_FREQ)

    # Delta curve normalized at 1000 Hz (index 17 in standard preferred frequencies)
    ideal_delta = (target_spl - target_spl[17]) - (ref_spl - ref_spl[17])

    # 2. Fit the filter gains using scipy.optimize.curve_fit
    initial_guess = [0.0] * len(BASE_FILTERS)
    optimized_gains, _ = curve_fit(fit_model, ISO_FREQ, ideal_delta, p0=initial_guess)

    # 3. Round and filter out zero-gain bands
    scaled_filters = []
    for i, (ftype, fc, _, q_val) in enumerate(BASE_FILTERS):
        scaled_gain = round(optimized_gains[i], 2)
        if scaled_gain != 0.0:
            scaled_filters.append((ftype, fc, scaled_gain, q_val))

    return scaled_filters


def calculate_headroom_offset(filters, fs=48000):
    """Calculates the headroom offset (negative gain) required to keep the response below 0 dB."""
    if not filters:
        return 0.0
    frequencies = np.logspace(np.log10(20), np.log10(20000), 1000)
    response_db = get_filter_response(filters, frequencies, fs)
    max_gain = np.max(response_db)
    if max_gain > 0.0:
        return -round(max_gain, 2)
    return 0.0


def write_markdown_table(filters, level, headroom_offset=0.0):
    """Writes a markdown table listing the PEQ filters to a file and prints it."""
    level_str = f"{int(level)}" if level.is_integer() else f"{level}"
    filename = f"filter-{level_str}db.md"

    lines = []
    lines.append(f"### Equal-Loudness Compensation EQ for {level} dB")
    if headroom_offset != 0.0:
        lines.append(f"*(Reference Level: {REF_LEVEL} dB, Headroom Adjustment: {headroom_offset:.2f} dB)*\n")
    else:
        lines.append(f"*(Reference Level: {REF_LEVEL} dB)*\n")

    if not filters:
        lines.append("No correction filters are needed for this playback level.\n")
    else:
        lines.append("| Band | Type | Center Frequency (Hz) | Amplitude (dB) | Q-Value |")
        lines.append("| :--- | :--- | :--- | :--- | :--- |")
        for i, filt in enumerate(filters, 1):
            lines.append(f"| {i} | {filt[0]} | {filt[1]} | {filt[2]:.2f} | {filt[3]:.2f} |")
        lines.append("\n")

    content = "\n".join(lines)
    print(content)

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Saved PEQ table to: {filename}")



def plot_frequency_response(filters, level, headroom_offset=0.0, fs=48000):
    """Plots the combined frequency response of the PEQ filters and saves to PNG."""
    frequencies = np.logspace(np.log10(20), np.log10(20000), 1000)

    # Convert magnitude to dB and apply headroom offset
    response_db = get_filter_response(filters, frequencies, fs) + headroom_offset

    # Plot setup
    plt.figure(figsize=(12, 6))
    plt.semilogx(frequencies, response_db, color='#1f77b4', linewidth=2, label='Compensated Response')

    title_str = f'Equal-Loudness PEQ Compensation ({level} dB Average Playback)'
    if headroom_offset != 0.0:
        title_str += f'\n(Headroom Adjustment: {headroom_offset:.2f} dB)'
    plt.title(title_str)

    plt.xlabel('Frequency (Hz)')
    plt.ylabel('Amplitude (dB)')
    plt.grid(True, which='both', linestyle='--', alpha=0.5)
    plt.xlim([20, 20000])

    # Set y-axis limits to accommodate scaling and 0 dB ceiling
    plt.ylim([
        min(np.min(response_db) - 1, -6),
        max(np.max(response_db) + 1, 2)
    ])

    # Add reference markers
    plt.axhline(0, color='r', linestyle='--', linewidth=1.2, label='Digital Clipping Limit (0 dB)')
    if headroom_offset != 0.0:
        plt.axhline(
            headroom_offset, color='black', linestyle=':', linewidth=1,
            label=f'Original Flat Reference ({headroom_offset:.2f} dB)'
        )

    plt.legend(loc='best')

    # Adjust x-axis ticks for standard audio plot visibility
    plt.xticks(
        [20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000],
        ['20', '50', '100', '200', '500', '1k', '2k', '5k', '10k', '20k']
    )

    plt.tight_layout()
    level_str = f"{int(level)}" if level.is_integer() else f"{level}"
    output_file = f"filter-{level_str}db.png"
    plt.savefig(output_file, dpi=150)
    plt.close()
    print(f"Saved frequency response plot to: {output_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Generate Equal-Loudness PEQ Filters')
    parser.add_argument('--level', type=float, default=65.0,
                        help='Target average playback level in dB (default: 65.0)')
    args = parser.parse_args()

    target_filters = calculate_filters_for_level(args.level)
    offset = calculate_headroom_offset(target_filters)
    write_markdown_table(target_filters, args.level, offset)
    plot_frequency_response(target_filters, args.level, offset)
