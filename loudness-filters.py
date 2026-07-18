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
from scipy.signal import freqz

# Standard reference level for flat playback
REF_LEVEL = 83.0

# Base EQ profile calculated for a 65 dB target (18 dB difference from reference)
# Format: (Type, Frequency, Gain_at_65dB, Q)
BASE_FILTERS = [
    ('Low Shelf', 35, 2.5, 0.71),
    ('Low Shelf', 75, 2.5, 0.71),
    ('Peak', 150, 1.0, 0.70),
    ('Peak', 300, 0.5, 1.00),
    ('Peak', 600, 0.2, 1.40),
    ('Peak', 1000, 0.0, 1.00),
    ('Peak', 3000, 0.2, 1.40),
    ('Peak', 6000, 0.5, 1.00),
    ('High Shelf', 10000, 0.8, 0.71),
    ('High Shelf', 16000, 1.0, 0.71),
]


def get_biquad_coefs(ftype, fc, fs, gain, q):
    """Generates biquad coefficients based on Robert Bristow-Johnson's Audio EQ Cookbook."""
    a_val = 10 ** (gain / 40.0)
    w0 = 2 * np.pi * fc / fs
    alpha = np.sin(w0) / (2 * q)

    if gain == 0:
        return [1.0, 0.0, 0.0], [1.0, 0.0, 0.0]

    if ftype == 'Peak':
        b0 = 1 + alpha * a_val
        b1 = -2 * np.cos(w0)
        b2 = 1 - alpha * a_val
        a0 = 1 + alpha / a_val
        a1 = -2 * np.cos(w0)
        a2 = 1 - alpha / a_val
    elif ftype == 'Low Shelf':
        b0 = a_val * ((a_val + 1) - (a_val - 1) * np.cos(w0) + 2 * np.sqrt(a_val) * alpha)
        b1 = 2 * a_val * ((a_val - 1) - (a_val + 1) * np.cos(w0))
        b2 = a_val * ((a_val + 1) - (a_val - 1) * np.cos(w0) - 2 * np.sqrt(a_val) * alpha)
        a0 = (a_val + 1) + (a_val - 1) * np.cos(w0) + 2 * np.sqrt(a_val) * alpha
        a1 = -2 * ((a_val - 1) + (a_val + 1) * np.cos(w0))
        a2 = (a_val + 1) + (a_val - 1) * np.cos(w0) - 2 * np.sqrt(a_val) * alpha
    elif ftype == 'High Shelf':
        b0 = a_val * ((a_val + 1) + (a_val - 1) * np.cos(w0) + 2 * np.sqrt(a_val) * alpha)
        b1 = -2 * a_val * ((a_val - 1) + (a_val + 1) * np.cos(w0))
        b2 = a_val * ((a_val + 1) - (a_val - 1) * np.cos(w0) - 2 * np.sqrt(a_val) * alpha)
        a0 = (a_val + 1) - (a_val - 1) * np.cos(w0) + 2 * np.sqrt(a_val) * alpha
        a1 = 2 * ((a_val - 1) - (a_val + 1) * np.cos(w0))
        a2 = (a_val + 1) - (a_val - 1) * np.cos(w0) - 2 * np.sqrt(a_val) * alpha
    else:
        raise ValueError(f"Unsupported filter type: {ftype}")

    return [b0/a0, b1/a0, b2/a0], [1.0, a1/a0, a2/a0]


def calculate_filters_for_level(target_level):
    """Scales the baseline 65dB EQ profile to the requested target level."""
    # Scale factor based on how far we are from 83 dB compared to 65 dB
    scale = (REF_LEVEL - target_level) / (REF_LEVEL - 65.0)

    scaled_filters = []
    for ftype, fc, base_gain, q in BASE_FILTERS:
        scaled_gain = round(base_gain * scale, 2)
        if scaled_gain != 0.0:
            scaled_filters.append((ftype, fc, scaled_gain, q))

    return scaled_filters


def write_markdown_table(filters, level):
    """Writes a markdown table listing the PEQ filters to a file and prints it."""
    level_str = f"{int(level)}" if level.is_integer() else f"{level}"
    filename = f"filter-{level_str}db.md"

    lines = []
    lines.append(f"### Equal-Loudness Compensation EQ for {level} dB")
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


def plot_frequency_response(filters, level, fs=48000):
    """Plots the combined frequency response of the PEQ filters and saves to PNG."""
    frequencies = np.logspace(np.log10(20), np.log10(20000), 1000)
    w_eval = 2 * np.pi * frequencies / fs

    # Initialize total frequency response array
    total_h = np.ones(len(frequencies), dtype=complex)

    for filt in filters:
        b, a = get_biquad_coefs(filt[0], filt[1], fs, filt[2], filt[3])
        total_h *= freqz(b, a, worN=w_eval)[1]

    # Convert magnitude to dB
    response_db = 20 * np.log10(np.abs(total_h))

    # Plot setup
    plt.figure(figsize=(12, 6))
    plt.semilogx(frequencies, response_db, color='#1f77b4', linewidth=2)
    plt.title(f'Equal-Loudness PEQ Compensation ({level} dB Average Playback)')
    plt.xlabel('Frequency (Hz)')
    plt.ylabel('Amplitude (dB)')
    plt.grid(True, which='both', linestyle='--', alpha=0.5)
    plt.xlim([20, 20000])

    # Set y-axis limits to accommodate scaling well
    plt.ylim([
        min(np.min(response_db) - 1, -2),
        max(np.max(response_db) + 2, 6)
    ])

    # Add reference markers
    plt.axhline(0, color='black', linewidth=1)

    # Adjust x-axis ticks for standard audio plot visibility
    plt.xticks(
        [20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000],
        ['20', '50', '100', '200', '500', '1k', '2k', '5k', '10k', '20k']
    )

    plt.tight_layout()
    level_str = f"{int(level)}" if level.is_integer() else f"{level}"
    output_file = f"filter-{level_str}db.png"
    plt.savefig(output_file, dpi=150)
    print(f"Saved frequency response plot to: {output_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Generate Equal-Loudness PEQ Filters')
    parser.add_argument('--level', type=float, default=65.0,
                        help='Target average playback level in dB (default: 65.0)')
    args = parser.parse_args()

    target_filters = calculate_filters_for_level(args.level)
    write_markdown_table(target_filters, args.level)
    plot_frequency_response(target_filters, args.level)
