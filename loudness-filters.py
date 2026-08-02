#!/usr/bin/env python
"""
Equal-loudness compensation filter generator.

Fits a parametric EQ to the ISO 226 equal-loudness compensation target for a
given listening level relative to a mastering reference level, and writes a
Markdown table, a CamillaDSP YAML file, and a frequency-response plot.

The filter set is nested: bands 1-5 are a complete, standalone full-spectrum
correction, and bands 6-10 refine it. A listener can enter five bands and stop.
"""

# pylint: disable=invalid-name

import argparse
import sys
import time

import numpy as np
import yaml
from scipy.optimize import minimize

from iso226_utils import (
    DESIGN_FS, EXTRAP_TOLERANCE_DB, ISO_FREQ, VERIFY_RATES,
    build_target, get_filter_response, ideal_delta, peak_gain,
)

# --- Parameter bounds -------------------------------------------------------
MIN_LEVEL = 50.0
MAX_LEVEL = 90.0
MIN_REFERENCE = 70.0
MAX_REFERENCE = 90.0
MIN_SCALE = 0.1
MAX_SCALE = 1.0

# Roon's MUSE Parametric EQ gain control spans +12 to -12 dB; miniDSP allows
# +/-16 dB, so 12 dB satisfies both. This bounds the per-band gain we may ask
# for and the preamp attenuation we may require.
MAX_BAND_GAIN = 12.0
MAX_HEADROOM = 12.0

# Roon accepts filter gains to one tenth of a dB. A band whose gain rounds to
# zero at that precision cannot do anything when entered by hand.
HOST_GAIN_PRECISION_DB = 0.1

# Anti-degeneracy: an unconstrained minimax fit will happily place two large,
# nearly cancelling filters at almost the same frequency (e.g. +17.33 dB at
# 396 Hz against -16.12 dB at 438 Hz). The end-to-end magnitude response is
# fine, and because RBJ biquads are minimum phase the phase cancels too -- so
# there is no pre-ringing. The damage is elsewhere:
#
#   * In a serial fixed-point chain (miniDSP and similar) the signal leaving the
#     boosting section is ~17 dB hot before the next section pulls it back, so
#     an intermediate node can overflow while the overall response looks clean.
#   * Published values are rounded, and host DSPs quantize further. A pair of
#     large opposing filters is a small difference of large numbers, so
#     quantization that would be negligible in isolation becomes a large net
#     magnitude error.
#   * It wastes headroom for no accuracy benefit.
#
# Three constraints remove the degenerate family: a budget on total absolute
# gain, non-overlapping frequency ranges within a tier, and a minimum spacing
# ratio between consecutive bands. The spacing constraint is what actually does
# the work -- non-overlapping ranges alone still allow two bands to meet at a
# shared range boundary, which is exactly where a cancelling pair forms.
GAIN_BUDGET_FACTOR = 2.0
REFINEMENT_GAIN_BUDGET_FACTOR = 0.4
MIN_REFINEMENT_GAIN_BUDGET = 2.0

# Consecutive bands must be at least this far apart in frequency (~3/4 octave).
MIN_SPACING_RATIO = 1.7

# If the fit cannot get within this of the target, the target is unreachable
# within the per-band gain budget and the request should be refused.
FIT_ERROR_LIMIT_DB = 1.0


def _progress(message, end="\n"):
    """Progress to stderr, so stdout stays usable for piping the tables."""
    print(message, end=end, file=sys.stderr, flush=True)


# --- Filter topology --------------------------------------------------------
# Both tiers span the full spectrum. Treble compensation belongs in the
# essential set: at low levels the loss of perceived treble is as consequential
# as the loss of bass, particularly for listeners with age-related HF loss.
#
# There is deliberately no band above 12 kHz. ISO 226 data stops at 12.5 kHz,
# and a 16 kHz shelf both extrapolates without evidence and behaves very
# differently across sample rates as it interacts with Nyquist.
#
# Frequency ranges within a tier are non-overlapping, so two bands of the same
# tier can never converge on the same frequency to form a cancelling pair.
LOW_SHELF, PEAK, HIGH_SHELF = 'Low Shelf', 'Peak', 'High Shelf'

TIER1_TYPES = [LOW_SHELF, PEAK, PEAK, PEAK, HIGH_SHELF]
TIER1_FC_BOUNDS = [(30.0, 120.0), (120.0, 450.0), (450.0, 1600.0),
                   (1600.0, 5500.0), (5500.0, 12000.0)]

TIER2_TYPES = [LOW_SHELF, PEAK, PEAK, PEAK, HIGH_SHELF]
TIER2_FC_BOUNDS = [(20.0, 80.0), (80.0, 300.0), (300.0, 1100.0),
                   (1100.0, 4000.0), (4000.0, 11000.0)]

TIER_SIZE = 5

MIN_Q, MAX_Q = 0.25, 2.0


def validate_parameters(target_level, ref_level, scale=1.0):
    """Validate the requested levels and scale against their allowed ranges."""
    if not MIN_LEVEL <= target_level <= MAX_LEVEL:
        raise ValueError(
            f"Target listening level ({target_level} dB) must be between "
            f"{MIN_LEVEL} and {MAX_LEVEL} dB SPL."
        )
    if not MIN_REFERENCE <= ref_level <= MAX_REFERENCE:
        raise ValueError(
            f"Reference (mastering) level ({ref_level} dB) must be between "
            f"{MIN_REFERENCE} and {MAX_REFERENCE} dB SPL."
        )
    if not MIN_SCALE <= scale <= MAX_SCALE:
        raise ValueError(
            f"Scale ({scale}) must be between {MIN_SCALE} and {MAX_SCALE}."
        )


def _fit_bands(types, fc_bounds, grid, target, in_band, gain_budget,
               fixed=(), restarts=4, seed=0):
    """Minimax fit of one group of bands, optionally on top of fixed bands.

    Solved in epigraph form -- minimize t subject to |error| <= t -- rather than
    by handing max(abs(error)) to a gradient optimizer. The maximum of absolute
    values is not differentiable at its optimum, which is exactly where the
    solver spends its time; the epigraph form is smooth and converges properly.

    In-band error drives the objective. Outside the ISO data range the error is
    merely constrained, so the extrapolation stays bounded without consuming
    the accuracy budget where the standard actually has evidence. Total absolute
    gain is capped by ``gain_budget`` to rule out large offsetting band pairs.
    """
    n = len(types)
    fixed = list(fixed)
    seeds = [float(np.sqrt(lo * hi)) for lo, hi in fc_bounds]
    bounds = (
        [(-MAX_BAND_GAIN, MAX_BAND_GAIN)] * n
        + list(fc_bounds)
        + [(MIN_Q, MAX_Q)] * n
    )

    def unpack(p):
        return [(types[i], p[n + i], p[i], p[2 * n + i]) for i in range(n)]

    def error(p):
        return get_filter_response(fixed + unpack(p), grid, DESIGN_FS) - target

    def in_band_error(p):
        return float(np.max(np.abs(error(p)[in_band])))

    def constraint(p):
        err = error(p)
        oob = np.concatenate([err[:in_band.start], err[in_band.stop:]])
        freqs = p[n:2 * n]
        spacing = freqs[1:] - MIN_SPACING_RATIO * freqs[:-1]
        return np.concatenate([
            p[3 * n] - err[in_band],
            p[3 * n] + err[in_band],
            EXTRAP_TOLERANCE_DB - np.abs(oob),
            [gain_budget - np.sum(np.abs(p[:n]))],
            spacing,
        ])

    rng = np.random.default_rng(seed)
    best_value, best_params = np.inf, None

    for attempt in range(restarts):
        if attempt == 0:
            gains, freqs, qs = [0.0] * n, list(seeds), [0.7] * n
        else:
            gains = list(rng.uniform(-2.0, 6.0, n))
            # Jitter is kept mild so restarts still satisfy MIN_SPACING_RATIO.
            freqs = [s * float(rng.uniform(0.85, 1.18)) for s in seeds]
            qs = list(rng.uniform(0.4, 1.1, n))
        start = np.array([
            min(max(v, lo), hi)
            for v, (lo, hi) in zip(gains + freqs + qs, bounds)
        ])
        x0 = np.concatenate([start, [in_band_error(start)]])

        result = minimize(
            lambda p: p[3 * n], x0, method='SLSQP',
            bounds=bounds + [(0.0, 60.0)],
            constraints=[{'type': 'ineq', 'fun': constraint}],
            options={'maxiter': 300, 'ftol': 1e-9},
        )
        value = in_band_error(result.x[:3 * n])
        if value < best_value:
            best_value, best_params = value, result.x[:3 * n]

    if best_params is None:
        raise RuntimeError("Filter optimization failed to produce any solution.")
    return best_value, unpack(best_params)


def _round_filters(filters):
    """Round to the precision a user can actually enter into a DSP."""
    return [(ftype, round(float(fc), 1), round(float(gain), 2), round(float(q), 2))
            for ftype, fc, gain, q in filters]


def calculate_filters(target_level, ref_level, scale=1.0):
    """Fit the nested two-tier filter set for a listening level.

    Bands 1-5 are fitted first and then held fixed while bands 6-10 are fitted
    on top of them, so the essential set is exactly the best standalone
    five-band solution rather than a by-product of a ten-band fit.

    Returns:
        dict with 'essential', 'refinement', 'all', 'error_essential',
        'error_all' -- errors measured from the rounded, published values.
    """
    validate_parameters(target_level, ref_level, scale)
    grid, target, in_band = build_target(target_level, ref_level, scale)

    span = float(np.ptp(target[in_band]))
    tier1_budget = GAIN_BUDGET_FACTOR * span
    tier2_budget = max(MIN_REFINEMENT_GAIN_BUDGET,
                       REFINEMENT_GAIN_BUDGET_FACTOR * span)

    _progress(f"Fitting listening level {_level_str(target_level)} dB against a "
              f"{ref_level:g} dB reference, scale {scale:.2f}.")
    # No time estimate: this is a constrained minimax with multistart, and how
    # long it takes depends entirely on the machine. Each tier reports its own
    # elapsed time instead, which is true everywhere.
    _progress("Constrained minimax with multistart; tens of seconds per tier "
              "on a typical desktop, longer on low-power hardware.")

    _progress("  bands 1-5  (essential) ...", end=" ")
    started = time.perf_counter()
    _, tier1 = _fit_bands(TIER1_TYPES, TIER1_FC_BOUNDS, grid, target, in_band,
                          tier1_budget, seed=3)
    tier1 = _round_filters(tier1)
    _progress(f"done ({time.perf_counter() - started:.1f} s)")

    _progress("  bands 6-10 (refinement) ...", end=" ")
    started = time.perf_counter()
    _, tier2 = _fit_bands(TIER2_TYPES, TIER2_FC_BOUNDS, grid, target, in_band,
                          tier2_budget, fixed=tier1, seed=5)
    tier2 = _round_filters(tier2)
    _progress(f"done ({time.perf_counter() - started:.1f} s)")

    def published_error(filters):
        resp = get_filter_response(filters, grid, DESIGN_FS)
        return float(np.max(np.abs((resp - target)[in_band])))

    return {
        'essential': tier1,
        'refinement': tier2,
        'all': tier1 + tier2,
        'error_essential': published_error(tier1),
        'error_all': published_error(tier1 + tier2),
    }


def headroom_adjustment(result):
    """Single conservative headroom figure covering both tiers, in 0.1 dB steps.

    Roon accepts one tenth of a dB, so the worst-case peak across both filter
    sets and all verified sample rates is rounded away from zero. A listener who
    enters only the essential five bands and one who enters all ten can use the
    same number without either of them clipping.
    """
    peak = max(peak_gain(result['essential']), peak_gain(result['all']))
    if peak <= 0.0:
        return 0.0
    return -np.ceil(peak * 10.0) / 10.0


def cascade_diagnostics(filters, trials=32, seed=11):
    """Conditioning metrics for a serial biquad chain.

    ``stage_peak`` is the largest gain reached at any intermediate point in the
    cascade. Hosts that run biquads serially in fixed point (miniDSP and
    similar) can overflow an intermediate node even when the end-to-end
    response is well behaved, so this wants to stay near the final peak.

    ``quantization_sensitivity`` is the worst magnitude deviation seen when the
    published values are jittered by about half a printed digit -- a proxy for
    the host DSP's own coefficient quantization. Large offsetting band pairs
    show up here, because their net effect is a small difference of large
    numbers and rounding no longer cancels.
    """
    grid = np.logspace(np.log10(20.0), np.log10(20000.0), 800)
    base = get_filter_response(filters, grid)
    stage_peak = max(float(np.max(get_filter_response(filters[:i + 1], grid)))
                     for i in range(len(filters)))
    rng = np.random.default_rng(seed)
    worst = 0.0
    for _ in range(trials):
        jittered = [
            (ftype,
             fc * (1.0 + float(rng.uniform(-0.001, 0.001))),
             gain + float(rng.uniform(-0.005, 0.005)),
             q + float(rng.uniform(-0.005, 0.005)))
            for ftype, fc, gain, q in filters
        ]
        worst = max(worst, float(np.max(np.abs(
            get_filter_response(jittered, grid) - base))))
    # Worst opposing neighbour: the largest pair of adjacent, opposite-sign
    # gains relative to how far apart they sit. High values mean the fit is
    # relying on cancellation rather than on shaping.
    opposing = 0.0
    ordered = sorted(filters, key=lambda f: f[1])
    for first, second in zip(ordered, ordered[1:]):
        if first[2] * second[2] < 0:
            octaves = abs(np.log2(second[1] / first[1]))
            overlap = min(abs(first[2]), abs(second[2]))
            opposing = max(opposing, overlap / max(octaves, 0.1))

    return {
        'final_peak': float(np.max(base)),
        'stage_peak': stage_peak,
        'gain_sum': float(sum(abs(f[2]) for f in filters)),
        'quantization_sensitivity': worst,
        'opposing_neighbours': float(opposing),
    }


SUGGESTION_MARGIN_DB = 0.5


def suggest_alternatives(target_level, ref_level, scale):
    """Compute a scale and a listening level that would fit the 12 dB budget.

    Estimated from the size of the *target* curve rather than from the peak of
    the failed fit: when a fit succeeds its peak gain tracks the maximum of the
    target, whereas a fit that has run out of per-band gain overshoots, which
    would make both suggestions needlessly conservative.
    """
    budget = MAX_HEADROOM - SUGGESTION_MARGIN_DB
    peak_target = float(np.max(np.abs(ideal_delta(target_level, ref_level, scale))))

    suggested_scale = None
    if peak_target > 0:
        raw = scale * budget / peak_target
        suggested_scale = float(np.floor(raw * 20.0) / 20.0)
        suggested_scale = max(MIN_SCALE, min(MAX_SCALE, suggested_scale))
        if suggested_scale >= scale:
            suggested_scale = None

    # Find the quietest listening level whose target still fits the budget.
    suggested_level = None
    already_fits = peak_target <= budget
    lo, hi = target_level, min(ref_level, MAX_LEVEL)
    reachable = float(np.max(np.abs(ideal_delta(hi, ref_level, scale)))) <= budget
    if not already_fits and reachable:
        for _ in range(60):
            mid = (lo + hi) / 2.0
            if float(np.max(np.abs(ideal_delta(mid, ref_level, scale)))) > budget:
                lo = mid
            else:
                hi = mid
        # Bisection converges from above, so nudge before rounding up: without
        # this a level that already fits comes back one dB higher than itself.
        suggested_level = float(np.ceil(hi - 1e-6))
        if suggested_level <= target_level:
            suggested_level = None
    return suggested_scale, suggested_level


def check_budget(result, target_level, ref_level, scale):
    """Raise a ValueError with actionable suggestions if the set cannot be used."""
    peak = max(peak_gain(result['essential']), peak_gain(result['all']))
    max_gain = max(abs(f[2]) for f in result['all'])
    unreachable = result['error_essential'] > FIT_ERROR_LIMIT_DB

    if peak <= MAX_HEADROOM and not unreachable:
        return

    reason = (
        f"the required headroom ({-peak:.2f} dB) exceeds the {MAX_HEADROOM:.1f} dB "
        f"available on Roon's Parametric EQ gain control"
        if peak > MAX_HEADROOM else
        f"the correction needs more than {MAX_BAND_GAIN:.0f} dB in a single band "
        f"(best achievable error {result['error_essential']:.2f} dB)"
    )
    sug_scale, sug_level = suggest_alternatives(target_level, ref_level, scale)
    lines = [
        f"Cannot build a usable filter set for --level {target_level:g} "
        f"--reference {ref_level:g}: {reason}.",
        f"  (largest single band gain in this fit: {max_gain:.2f} dB)",
        "",
        "Try one of:",
    ]
    if sug_scale is not None:
        lines.append(f"  --scale {sug_scale:.2f}      apply partial compensation "
                     f"(about {sug_scale * 100:.0f}% of the theoretical curve)")
    if sug_level is not None:
        lines.append(f"  --level {sug_level:g}       target a higher listening level")
    lines.append(f"  --reference <lower>  if this recording is mastered quieter "
                 f"than {ref_level:g} dB")
    raise ValueError("\n".join(lines))


# --- Output -----------------------------------------------------------------

DEFAULT_REFERENCE = 83.0


def _level_str(level):
    return f"{int(level)}" if float(level).is_integer() else f"{level}"


def _scale_str(scale):
    """1.0 -> '1.0', 0.75 -> '0.75' -- never a bare integer, never trailing noise."""
    text = f"{scale:g}"
    return text if "." in text else f"{text}.0"


def preset_stem(level, ref_level, scale):
    """Filename stem encoding what a preset actually is.

    A compensation curve is defined by the *pair* of levels, not by the
    listening level alone, so the reference belongs in the name. Scale is
    included so taste variants sit alongside each other without collision.
    """
    return (f"filter_{_level_str(ref_level)}_to_{_level_str(level)}"
            f"_s{_scale_str(scale)}")


def _filter_rows(filters, start=1):
    return [f"| {i} | {f[0]} | {f[1]} | {f[2]:.2f} | {f[3]:.2f} |"
            for i, f in enumerate(filters, start)]


TABLE_HEAD = [
    "| Band | Type | Center Frequency (Hz) | Amplitude (dB) | Q-Value |",
    "| :--- | :--- | :--- | :--- | :--- |",
]


def is_null_correction(result):
    """True when every band rounds to zero at the host's entry precision.

    Happens when the listening level equals the mastering reference: the ideal
    correction is identically zero, and the honest output is a sentence rather
    than ten bands of 0.00 dB. The preset still ships, because a listener at
    their reference level needs to be told to apply nothing -- without it they
    would reach for the nearest rung and apply a correction they do not need.
    """
    return all(abs(f[2]) < HOST_GAIN_PRECISION_DB / 2 for f in result['all'])


def write_markdown_table(result, level, ref_level, scale, headroom, filename):
    """Write the two-tier PEQ table."""
    if is_null_correction(result):
        content = "\n".join([
            f"### No Compensation Needed at {_level_str(level)} dB",
            "",
            f"*Mastering reference {ref_level:g} dB"
            + (" (default)" if ref_level == DEFAULT_REFERENCE else "")
            + f" · listening level {_level_str(level)} dB · scale {scale:.2f}*",
            "",
            "You are listening at the level this recording was mastered for, so "
            "there is nothing to correct: the ideal equal-loudness compensation "
            "here is 0.00 dB at every frequency.",
            "",
            "**Apply no filters and no headroom adjustment.** If you are using a "
            "preset from another listening level, disable it.",
            "",
            "This file exists so that the ladder covers your case explicitly. "
            "Reaching for the nearest neighbouring preset instead would apply "
            "about 1.6 dB of correction you do not want.",
            "",
        ])
        with open(filename, 'w', encoding='utf-8') as handle:
            handle.write(content)
        print(content)
        print(f"Saved PEQ table to: {filename}")
        return

    lines = [
        f"### Equal-Loudness Compensation EQ for {_level_str(level)} dB",
        "",
        f"*Mastering reference {ref_level:g} dB"
        + (" (default)" if ref_level == DEFAULT_REFERENCE else "")
        + f" · listening level {_level_str(level)} dB"
        + f" · scale {scale:.2f} · designed at {DESIGN_FS / 1000:.1f} kHz*",
        "",
        f"**Headroom adjustment: {headroom:.1f} dB.** Apply this as a negative "
        "preamp / headroom setting. It is the worst case across "
        f"{'/'.join(f'{r / 1000:g}' for r in VERIFY_RATES)} kHz and is safe for "
        "either the essential five bands or all ten.",
        "",
        f"#### Essential — bands 1–5 (max residual error {result['error_essential']:.4f} dB)",
        "",
        "A complete full-spectrum correction on its own. Enter these five and stop "
        "if you like.",
        "",
    ]
    lines += TABLE_HEAD + _filter_rows(result['essential']) + [""]
    lines += [
        f"#### Refinement — bands 6–10, optional "
        f"(max residual error with all ten: {result['error_all']:.4f} dB)",
        "",
        "These reduce the residual error further. Compare the two traces in the "
        "verification plot before deciding whether the extra entry is worth it.",
        "",
    ]
    if all(abs(f[2]) < HOST_GAIN_PRECISION_DB / 2 for f in result['refinement']):
        lines += [
            f"> **These bands round to 0.00 dB at the {HOST_GAIN_PRECISION_DB:.1f} dB "
            "entry precision Roon and most DSPs accept, so typing them in by hand "
            "changes nothing.** Five bands have already tracked the ISO 226 target "
            "to well below audibility; there is no residual left for them to "
            "correct. They are kept in the YAML because loading a file costs "
            "nothing, and listed here so the claim can be checked rather than "
            "taken on trust.",
            "",
        ]
    lines += TABLE_HEAD + _filter_rows(result['refinement'], start=TIER_SIZE + 1) + [""]

    content = "\n".join(lines)
    with open(filename, 'w', encoding='utf-8') as handle:
        handle.write(content)
    print(content)
    print(f"Saved PEQ table to: {filename}")


def write_camilladsp_yaml(result, level, ref_level, scale, headroom, filename):
    """Write all ten bands as a CamillaDSP YAML file for direct REW import."""
    type_map = {LOW_SHELF: 'Lowshelf', HIGH_SHELF: 'Highshelf', PEAK: 'Peaking'}
    filters = {}
    for i, (ftype, fc, gain, q_val) in enumerate(result['all'], 1):
        filters[f"band_{i}"] = {
            'type': 'Biquad',
            'parameters': {
                'type': type_map[ftype],
                'freq': float(fc),
                'gain': float(gain),
                'q': float(q_val),
            },
        }

    if is_null_correction(result):
        header = [
            f"# No compensation needed at {_level_str(level)} dB.",
            f"# Listening level equals the mastering reference "
            f"({ref_level:g} dB), so the ideal correction is 0.00 dB at every",
            "# frequency. Apply no filters and no headroom adjustment.",
            "# The bands below are all zero-gain and are included only so this",
            "# file is a valid, loadable CamillaDSP configuration.",
            "",
        ]
    else:
        header = [
            f"# Equal-Loudness Compensation EQ for {_level_str(level)} dB",
            f"# Mastering reference: {ref_level:g} dB"
            + ("  (default)" if ref_level == DEFAULT_REFERENCE else "")
            + f" · listening level: {_level_str(level)} dB · scale: {scale:.2f}",
            f"# Headroom adjustment: {headroom:.1f} dB "
            f"(apply as negative preamp gain)",
            f"# Designed at {DESIGN_FS / 1000:.1f} kHz.",
            f"# Bands 1-{TIER_SIZE} are a complete correction on their own "
            f"(max error {result['error_essential']:.4f} dB);",
            f"# bands {TIER_SIZE + 1}-10 refine it to {result['error_all']:.4f} dB.",
            "",
        ]
    body = yaml.dump({'filters': filters}, sort_keys=False, default_flow_style=False)
    with open(filename, 'w', encoding='utf-8') as handle:
        handle.write("\n".join(header) + body)
    print(f"Saved CamillaDSP YAML file to: {filename}")


def plot_frequency_response(result, level, ref_level, scale, headroom, filename):
    """Plot essential-only and full responses against the ideal target."""
    # Imported lazily and deliberately: matplotlib costs about a second to
    # import, and nothing else in this module needs it. Hoisting it to the top
    # would slow every CLI invocation, including the ones that only print a
    # table or fail validation.
    # pylint: disable=import-outside-toplevel
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    freqs = np.logspace(np.log10(20), np.log10(20000), 2000)
    resp5 = get_filter_response(result['essential'], freqs) + headroom
    resp10 = get_filter_response(result['all'], freqs) + headroom
    target = np.interp(np.log10(freqs), np.log10(ISO_FREQ),
                       ideal_delta(level, ref_level, scale)) + headroom

    plt.figure(figsize=(12, 6))
    plt.semilogx(freqs, target, color='#7f7f7f', linewidth=3, alpha=0.45,
                 label='Ideal ISO 226 target')
    plt.semilogx(freqs, resp10, color='#1f77b4', linewidth=2,
                 label=f"All 10 bands (max error {result['error_all']:.4f} dB)")
    plt.semilogx(freqs, resp5, color='#ff7f0e', linewidth=1.6, linestyle='--',
                 label=f"Essential 5 bands (max error {result['error_essential']:.4f} dB)")

    plt.axhline(0, color='#d62728', linestyle='--', linewidth=1.2,
                label='Digital clipping limit (0 dB)')
    plt.axhline(headroom, color='black', linestyle=':', linewidth=1,
                label=f'Flat reference ({headroom:.1f} dB)')
    plt.axvspan(12500, 20000, color='#999999', alpha=0.12,
                label='Beyond ISO 226 data (extrapolated)')

    plt.title(
        f'Equal-Loudness PEQ Compensation — listening at {_level_str(level)} dB, '
        f'mastered for {ref_level:g} dB'
        + (' (default)' if ref_level == DEFAULT_REFERENCE else '')
        + (f', scale {scale:.2f}' if scale != 1.0 else '') + '\n'
        f'Headroom adjustment {headroom:.1f} dB · designed at '
        f'{DESIGN_FS / 1000:.1f} kHz'
    )
    plt.xlabel('Frequency (Hz)')
    plt.ylabel('Amplitude (dB)')
    plt.grid(True, which='both', linestyle='--', alpha=0.5)
    plt.xlim([20, 20000])
    lo = min(np.min(resp10), np.min(resp5), headroom) - 1
    plt.ylim([min(lo, -6), max(np.max(resp10) + 1, 2)])
    plt.xticks([20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000],
               ['20', '50', '100', '200', '500', '1k', '2k', '5k', '10k', '20k'])
    plt.legend(loc='best', fontsize=9)
    plt.tight_layout()
    plt.savefig(filename, dpi=150)
    plt.close()
    print(f"Saved frequency response plot to: {filename}")


def main():
    """Parse arguments, fit the filter set, and write all output files."""
    parser = argparse.ArgumentParser(
        description='Generate equal-loudness compensation PEQ filters.')
    parser.add_argument('--level', type=float, required=True,
                        help=f'Measured listening level in dB SPL, at the '
                             f'listening position (required, range: '
                             f'{MIN_LEVEL}-{MAX_LEVEL}). There is no default: '
                             f'this is a property of your room, not of the '
                             f'recording.')
    parser.add_argument('--reference', type=float, default=DEFAULT_REFERENCE,
                        help=f'Level the recording was mastered for, in dB SPL '
                             f'(default: 83.0, range: {MIN_REFERENCE}-{MAX_REFERENCE})')
    parser.add_argument('--scale', type=float, default=1.0,
                        help=f'Fraction of the theoretical correction to apply '
                             f'(default: 1.0, range: {MIN_SCALE}-{MAX_SCALE})')
    args = parser.parse_args()

    try:
        validate_parameters(args.level, args.reference, args.scale)
        result = calculate_filters(args.level, args.reference, args.scale)
        check_budget(result, args.level, args.reference, args.scale)
    except ValueError as err:
        print(f"Error: {err}", file=sys.stderr)
        return 1

    headroom = headroom_adjustment(result)
    diag = cascade_diagnostics(result['all'])
    print(f"Cascade conditioning: final peak {diag['final_peak']:+.2f} dB, "
          f"worst intermediate stage {diag['stage_peak']:+.2f} dB, "
          f"total |gain| {diag['gain_sum']:.2f} dB, "
          f"quantization sensitivity {diag['quantization_sensitivity']:.4f} dB, "
          f"opposing neighbours {diag['opposing_neighbours']:.2f} dB/octave")

    stem = preset_stem(args.level, args.reference, args.scale)
    write_markdown_table(result, args.level, args.reference, args.scale,
                         headroom, f"{stem}.md")
    write_camilladsp_yaml(result, args.level, args.reference, args.scale,
                          headroom, f"{stem}.yml")
    plot_frequency_response(result, args.level, args.reference, args.scale,
                            headroom, f"{stem}.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
