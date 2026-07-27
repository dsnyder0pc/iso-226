#!/usr/bin/env python
"""
Loudness compensation filter generator.

Generates parametric EQ (PEQ) filters based on ISO 226 equal-loudness
contours relative to a reference level (83 dB), saves them to a Markdown
table file, and plots the combined frequency response to a PNG file.
"""

# pylint: disable=invalid-name

import argparse
import sys
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit, minimize
from iso226_utils import ISO_FREQ, iso226_spl, get_filter_response

# Standard reference level for flat playback
REF_LEVEL = 83.0

# Parameter boundary constants
MIN_LEVEL = 50.0
MAX_LEVEL = 90.0
MIN_REFERENCE = 70.0
MAX_REFERENCE = 90.0
MAX_ATTENUATION_LIMIT = 12.0


def validate_parameters(target_level, ref_level):
    """Validates target level, reference level, and parameter bounds."""
    if not (MIN_LEVEL <= target_level <= MAX_LEVEL):
        raise ValueError(
            f"Target playback level ({target_level} dB) must be between "
            f"{MIN_LEVEL} and {MAX_LEVEL} dB SPL."
        )
    if not (MIN_REFERENCE <= ref_level <= MAX_REFERENCE):
        raise ValueError(
            f"Reference playback level ({ref_level} dB) must be between "
            f"{MIN_REFERENCE} and {MAX_REFERENCE} dB SPL."
        )


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


def _calculate_ideal_delta(target_level, ref_level=None):
    """Calculates ideal delta curve normalized at 1000 Hz."""
    if ref_level is None:
        ref_level = REF_LEVEL
    ref_spl = iso226_spl(ref_level, ISO_FREQ)
    target_spl = iso226_spl(target_level, ISO_FREQ)
    return (target_spl - target_spl[17]) - (ref_spl - ref_spl[17])


def _optimize_filter_params(ideal_delta):
    """Fits filter gains, center frequencies, and Q-values using curve_fit and SLSQP."""
    def fit_gains(freqs, *gains):
        filters = [(BASE_FILTERS[i][0], BASE_FILTERS[i][1], gains[i], BASE_FILTERS[i][3])
                   for i in range(len(BASE_FILTERS))]
        return get_filter_response(filters, freqs)

    initial_guess = [0.0] * len(BASE_FILTERS)
    popt_gains, _ = curve_fit(fit_gains, ISO_FREQ, ideal_delta, p0=initial_guess)

    def loss_inf(params):
        filters = [(BASE_FILTERS[i][0], params[10 + i], params[i], params[20 + i])
                   for i in range(10)]
        resp = get_filter_response(filters, ISO_FREQ)
        return np.max(np.abs(resp - ideal_delta))

    p0 = list(popt_gains) + [f[1] for f in BASE_FILTERS] + [f[3] for f in BASE_FILTERS]

    bounds = []
    # Gains: -30.0 to 30.0 dB
    for _ in range(10):
        bounds.append((-30.0, 30.0))
    # Frequencies: +/- 30% of base frequencies
    for f in BASE_FILTERS:
        base_f = f[1]
        bounds.append((base_f * 0.70, base_f * 1.30))
    # Q-values: 0.3 to 3.0
    for _ in range(10):
        bounds.append((0.3, 3.0))

    res = minimize(loss_inf, p0, method='SLSQP', bounds=bounds, options={'maxiter': 500})
    return res.x[:10], res.x[10:20], res.x[20:30]


def calculate_filters_for_level(target_level, ref_level=None):
    """Optimizes the EQ profile to fit the ISO 226 target delta curve at the requested target level,

    minimizing maximum residual error across preferred frequencies.
    """
    if ref_level is None:
        ref_level = REF_LEVEL
    validate_parameters(target_level, ref_level)
    ideal_delta = _calculate_ideal_delta(target_level, ref_level)
    gains_opt, fcs_opt, qs_opt = _optimize_filter_params(ideal_delta)

    scaled_filters = []
    for i, (ftype, _, _, _) in enumerate(BASE_FILTERS):
        fc_val = round(float(fcs_opt[i]), 1) if not float(fcs_opt[i]).is_integer() else int(fcs_opt[i])
        scaled_gain = round(float(gains_opt[i]), 2)
        if scaled_gain != 0.0:
            scaled_filters.append((ftype, fc_val, scaled_gain, round(float(qs_opt[i]), 2)))

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



def plot_frequency_response(filters, level, headroom_offset=0.0, fs=48000, ref_level=None):
    """Plots the combined frequency response of the PEQ filters and saves to PNG."""
    if ref_level is None:
        ref_level = REF_LEVEL
    frequencies = np.logspace(np.log10(20), np.log10(20000), 1000)

    # Convert magnitude to dB and apply headroom offset
    response_db = get_filter_response(filters, frequencies, fs) + headroom_offset

    # Plot setup
    plt.figure(figsize=(12, 6))
    plt.semilogx(frequencies, response_db, color='#1f77b4', linewidth=2, label='Compensated Response')

    level_str = f"{int(level)}" if level.is_integer() else f"{level}"
    ref_str = f"{int(ref_level)}" if ref_level.is_integer() else f"{ref_level}"
    title_str = f'Equal-Loudness PEQ Compensation ({level_str} dB referenced to {ref_str} dB)'
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


def _build_camilladsp_yaml(filters, level, headroom_offset):
    """Generates CamillaDSP YAML formatted string."""
    type_map = {'Low Shelf': 'Lowshelf', 'High Shelf': 'Highshelf', 'Peak': 'Peaking'}
    lines = [
        f"# Equal-Loudness Compensation EQ for {level} dB",
        f"# Reference Level: {REF_LEVEL} dB, Headroom Adjustment: {headroom_offset:.2f} dB",
        "",
        "filters:"
    ]
    for i, (ftype, fc, gain, q_val) in enumerate(filters, 1):
        lines.extend([
            f"  band_{i}:",
            "    type: Biquad",
            "    parameters:",
            f"      type: {type_map.get(ftype, ftype)}",
            f"      freq: {fc:.1f}",
            f"      gain: {gain:.2f}",
            f"      q: {q_val:.2f}"
        ])
    return "\n".join(lines) + "\n"


def write_camilladsp_yaml(filters, level, headroom_offset=0.0):
    """Writes PEQ filters to a CamillaDSP YAML file formatted for REW import."""
    level_str = f"{int(level)}" if level.is_integer() else f"{level}"
    filename = f"filter-{level_str}db.yml"
    yaml_content = _build_camilladsp_yaml(filters, level, headroom_offset)

    with open(filename, 'w', encoding='utf-8') as f_out:
        f_out.write(yaml_content)
    print(f"Saved CamillaDSP YAML file to: {filename}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Generate Equal-Loudness PEQ Filters')
    parser.add_argument('--level', type=float, default=65.0,
                        help=f'Target average playback level in dB (default: 65.0, range: {MIN_LEVEL}-{MAX_LEVEL})')
    parser.add_argument('--reference', type=float, default=83.0,
                        help=f'Reference level for flat playback in dB (default: 83.0, range: {MIN_REFERENCE}-{MAX_REFERENCE})')
    args = parser.parse_args()

    REF_LEVEL = args.reference

    try:
        validate_parameters(args.level, args.reference)
        target_filters = calculate_filters_for_level(args.level, args.reference)
        offset = calculate_headroom_offset(target_filters)

        if abs(offset) > MAX_ATTENUATION_LIMIT:
            raise ValueError(
                f"Required headroom adjustment ({offset:.2f} dB) exceeds maximum allowed attenuation "
                f"limit of -{MAX_ATTENUATION_LIMIT:.1f} dB. Please select a higher target --level or a lower --reference level."
            )

        write_markdown_table(target_filters, args.level, offset)
        write_camilladsp_yaml(target_filters, args.level, offset)
        plot_frequency_response(target_filters, args.level, offset, ref_level=REF_LEVEL)
    except ValueError as err:
        print(f"Error: {err}", file=sys.stderr)
        sys.exit(1)
