#!/usr/bin/env python
"""
Equal-loudness compensation filter generator.

Fits a parametric EQ to the ISO 226 equal-loudness compensation target for a
given listening level relative to a mastering reference level, and writes a
Markdown table, a CamillaDSP YAML file, and a frequency-response plot.

The filter set is a single group of five bands spanning the full spectrum.
An earlier version published a second group of five "refinement" bands on top
of them; measurement showed those bands changed the response by less than the
rounding applied to publish them, so they were removed rather than asking
anyone to type filters that do nothing.
"""

# pylint: disable=invalid-name

import argparse
import sys
import time
from dataclasses import replace

import numpy as np
import yaml
from scipy.optimize import minimize

from iso226_utils import (
    DEFAULT_REFERENCE, DEFAULT_SCALE, DESIGN_FS, EXTRAP_TOLERANCE_DB, ISO_FREQ,
    MAX_LEVEL, MAX_SCALE, MIN_LEVEL, MIN_REFERENCE, MAX_REFERENCE, MIN_SCALE,
    VERIFY_RATES, Compensation, build_target, get_filter_response, ideal_delta,
    peak_gain,
)

# Roon's MUSE Parametric EQ gain control spans +12 to -12 dB; miniDSP allows
# +/-16 dB, so 12 dB satisfies both. This bounds the per-band gain we may ask
# for and the preamp attenuation we may require.
MAX_BAND_GAIN = 12.0
MAX_HEADROOM = 12.0

# Roon accepts filter gains to one tenth of a dB. A band whose gain rounds to
# zero at that precision cannot do anything when entered by hand.
HOST_GAIN_PRECISION_DB = 0.1

# --- Publication precision --------------------------------------------------
# Roon's collapsed filter list renders frequency as an integer, gain to 0.1 dB
# and Q to 0.01, but that is display only: entering 100.4 Hz and entering
# 100.0 Hz produce visibly different response curves, so the full float is
# stored and used. What we publish is therefore chosen from what changes the
# response, not from what the host echoes back.
#
# Measured, per band, as the step that moves the cascade by 0.005 dB:
#
#   * Sensitivity tracks gain x Q, not frequency. The high shelf is the most
#     demanding band in the set (0.08% at 9.9 kHz, because it carries +4.6 dB),
#     while the low-gain interior peaks tolerate 1-2%. A fixed number of decimal
#     places is the wrong shape for a column spanning three decades: 0.1 Hz is
#     marginal at 38 Hz and a hundred times finer than needed at 9.9 kHz.
#     Four significant figures holds >=10x margin at both ends.
#   * Q is the sensitive parameter by roughly twenty times. At 0.1 it costs
#     0.17-0.37 dB; at 0.01 it costs 0.010-0.017 dB and becomes the floor under
#     the whole published format.
#   * Gain at 0.1 dB costs 0.016-0.063 dB; at 0.01 dB it costs 0.002-0.004 dB,
#     which is already below the floor Q sets. A third decimal buys nothing.
FREQ_SIGNIFICANT_DIGITS = 4
GAIN_DECIMALS = 2
Q_DECIMALS = 2

# --- Search termination -----------------------------------------------------
# The fit is a non-convex minimax solved by a local method (SLSQP) from several
# starting points; a restart is one complete solve. The objective is the error
# of the ROUNDED values, because that is what ships -- scoring on the raw fit
# lets a restart win that is better before rounding and worse after, which was
# observed to make the 62 dB preset 16% worse when the restart count was raised.
PUBLISHED_ERROR_TARGET_DB = 0.05

# Restarts are independent draws, so the chance of never finding a good basin
# decays geometrically and the tail is long. Stop early when the search has
# clearly settled, and cap it so an unreachable target cannot spin forever.
MAX_RESTARTS = 24
STAGNATION_LIMIT = 6

# Meeting the target does not end the search on its own. The deterministic first
# attempt often clears it at the easy end of the ladder, and exiting there ships
# whatever that one guess happened to find: at 83 -> 80 dB it doubled the
# published error (0.0218 -> 0.0440 dB) purely because the search stopped before
# looking anywhere else. Give every level at least this many draws before the
# target is allowed to cut the search short.
MIN_RESTARTS = 6

# A returned point counts as feasible only if every constraint holds to this
# tolerance. SLSQP can exit without converging and return a point that fits
# well in band while violating the gain budget or the extrapolation bound.
CONSTRAINT_TOLERANCE = 1e-6

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
# gain, non-overlapping per-band frequency ranges, and a minimum spacing ratio
# between consecutive bands. The spacing constraint is what actually does the
# work -- non-overlapping ranges alone still allow two bands to meet at a
# shared range boundary, which is exactly where a cancelling pair forms.
GAIN_BUDGET_FACTOR = 2.0

# Consecutive bands must be at least this far apart in frequency (~3/4 octave).
MIN_SPACING_RATIO = 1.7

# If the fit cannot get within this of the target, the target is unreachable
# within the per-band gain budget and the request should be refused.
FIT_ERROR_LIMIT_DB = 1.0


def _progress(message, end="\n"):
    """Progress to stderr, so stdout stays usable for piping the tables."""
    print(message, end=end, file=sys.stderr, flush=True)


# --- Filter topology --------------------------------------------------------
# The set spans the full spectrum. Treble compensation belongs in it as much as
# bass: at low levels the loss of perceived treble is as consequential, and
# more so for listeners with age-related HF loss.
#
# There is deliberately no band above 12 kHz. ISO 226 data stops at 12.5 kHz,
# and a 16 kHz shelf both extrapolates without evidence and behaves very
# differently across sample rates as it interacts with Nyquist.
#
# Frequency ranges are non-overlapping, so two bands can never converge on the
# same frequency to form a cancelling pair. These bounds are hand-tuned and
# earn it: replacing them with even log spacing over the same span costs a
# factor of five in published error (0.027 dB -> 0.133 dB at 83 -> 74 dB).
LOW_SHELF, PEAK, HIGH_SHELF = 'Low Shelf', 'Peak', 'High Shelf'

BAND_TYPES = [LOW_SHELF, PEAK, PEAK, PEAK, HIGH_SHELF]
BAND_FC_BOUNDS = [(30.0, 120.0), (120.0, 450.0), (450.0, 1600.0),
                  (1600.0, 5500.0), (5500.0, 12000.0)]

BAND_COUNT = len(BAND_TYPES)

MIN_Q, MAX_Q = 0.25, 2.0


def _sigfig(value, digits):
    """Round to a fixed number of significant figures."""
    if value == 0:
        return 0.0
    return float(round(value, -int(np.floor(np.log10(abs(value)))) + digits - 1))


def publication_round(filters):
    """Round to the precision the Markdown table publishes.

    Frequency carries significant figures rather than decimal places because
    its sensitivity is fractional; gain and Q carry decimals. See the
    publication-precision notes at the top of this module for the measurements
    behind each choice.
    """
    return [(ftype,
             _sigfig(float(fc), FREQ_SIGNIFICANT_DIGITS),
             round(float(gain), GAIN_DECIMALS),
             round(float(q), Q_DECIMALS))
            for ftype, fc, gain, q in filters]


def _restart_point(attempt, rng, seeds, bounds):
    """Starting point for one multistart attempt, clipped into ``bounds``.

    Attempt 1 is the deterministic neutral guess: flat gains, every band at the
    geometric mean of its own frequency range, mid Q. Later attempts randomize,
    with the frequency jitter kept mild so a restart still satisfies
    MIN_SPACING_RATIO before the solver has done anything.
    """
    n = len(seeds)
    if attempt == 1:
        values = [0.0] * n + list(seeds) + [0.7] * n
    else:
        values = (list(rng.uniform(-2.0, 6.0, n))
                  + [s * float(rng.uniform(0.85, 1.18)) for s in seeds]
                  + list(rng.uniform(0.4, 1.1, n)))
    return np.array([min(max(v, lo), hi)
                     for v, (lo, hi) in zip(values, bounds)])


class _Objective:
    """Error and constraints for one band layout against one fit target.

    Kept apart from the multistart loop because they are separate concerns:
    this knows about filters and the ISO target, the loop knows about restarts.

    The problem is posed in epigraph form -- minimize t subject to
    |error| <= t -- rather than by handing max(abs(error)) to a gradient
    optimizer. The maximum of absolute values is not differentiable at its
    optimum, which is exactly where the solver spends its time; the epigraph
    form is smooth and converges properly. The parameter vector is therefore
    ``[gains, freqs, qs, t]``.

    In-band error drives the objective. Outside the ISO data range the error is
    merely constrained, so the extrapolation stays bounded without consuming the
    accuracy budget where the standard actually has evidence. Total absolute
    gain is capped to rule out large offsetting band pairs.
    """

    def __init__(self, types, fc_bounds, fit, gain_budget):
        self.types = types
        self.n = len(types)
        self.fit = fit
        self.gain_budget = gain_budget
        self.seeds = [float(np.sqrt(lo * hi)) for lo, hi in fc_bounds]
        self.bounds = (
            [(-MAX_BAND_GAIN, MAX_BAND_GAIN)] * self.n
            + list(fc_bounds)
            + [(MIN_Q, MAX_Q)] * self.n
        )

    def unpack(self, p):
        """Parameter vector -> (type, fc, gain, q) tuples."""
        n = self.n
        return [(self.types[i], p[n + i], p[i], p[2 * n + i]) for i in range(n)]

    def error(self, p):
        """Signed deviation from the target across the whole design grid."""
        return get_filter_response(
            self.unpack(p), self.fit.grid, DESIGN_FS) - self.fit.target

    def in_band_error(self, p):
        """Worst deviation inside the ISO-backed span -- the fit objective."""
        return float(np.max(np.abs(self.error(p)[self.fit.in_band])))

    def published_error(self, filters):
        """Error of already-rounded filters -- what the reader actually gets."""
        response = get_filter_response(filters, self.fit.grid, DESIGN_FS)
        return float(np.max(np.abs(
            (response - self.fit.target)[self.fit.in_band])))

    def constraint(self, p):
        """Inequality vector for SLSQP; every entry must stay non-negative.

        Epigraph bounds on the in-band error, the extrapolation tolerance
        outside it, the total gain budget, and the minimum spacing between
        consecutive bands.
        """
        n, in_band = self.n, self.fit.in_band
        err = self.error(p)
        oob = np.concatenate([err[:in_band.start], err[in_band.stop:]])
        freqs = p[n:2 * n]
        return np.concatenate([
            p[3 * n] - err[in_band],
            p[3 * n] + err[in_band],
            EXTRAP_TOLERANCE_DB - np.abs(oob),
            [self.gain_budget - np.sum(np.abs(p[:n]))],
            freqs[1:] - MIN_SPACING_RATIO * freqs[:-1],
        ])

    def feasible(self, x):
        """Whether a returned point actually satisfies every constraint.

        SLSQP can exit without converging and hand back a point that fits well
        in band while breaking the gain budget or the extrapolation bound.
        Nothing downstream re-checks those, so they are checked here.
        """
        return bool(np.min(self.constraint(x)) >= -CONSTRAINT_TOLERANCE)


def _solve_once(obj, start):
    """One SLSQP solve from ``start``.

    Returns the published (rounded) filters and their error, or None if the
    solve did not converge or landed outside the feasible region.
    """
    x0 = np.concatenate([start, [obj.in_band_error(start)]])
    result = minimize(
        lambda p: p[3 * obj.n], x0, method='SLSQP',
        bounds=obj.bounds + [(0.0, 60.0)],
        constraints=[{'type': 'ineq', 'fun': obj.constraint}],
        options={'maxiter': 300, 'ftol': 1e-9},
    )
    if not result.success or not obj.feasible(result.x):
        return None
    filters = publication_round(obj.unpack(result.x[:3 * obj.n]))
    return filters, obj.published_error(filters)


def _fit_bands(types, fc_bounds, fit, gain_budget, seed=0):
    """Multistart search for the published band set with the smallest error.

    SLSQP is a local method and this problem is not convex, so each attempt
    solves from a different starting point and the best survives. Two rules make
    running the search longer monotonically safe, which the target-driven exit
    depends on:

      * an attempt is scored on its PUBLISHED error, so the winner is whichever
        set is best *after* rounding. Scoring on the raw fit lets an attempt win
        that is better before rounding and worse after -- which is not
        hypothetical: it made the 62 dB preset 16% worse (0.0986 -> 0.1140 dB)
        when the restart count was raised.
      * an attempt is discarded unless it converged and is feasible.

    Returns:
        dict with 'filters' (rounded), 'error' (published), the number of
        'restarts' spent and whether 'target_met'.
    """
    obj = _Objective(types, fc_bounds, fit, gain_budget)
    rng = np.random.default_rng(seed)
    best_error, best_filters = np.inf, None
    since_improved, attempt = 0, 0

    for attempt in range(1, MAX_RESTARTS + 1):
        found = _solve_once(
            obj, _restart_point(attempt, rng, obj.seeds, obj.bounds))
        improved = found is not None and found[1] < best_error
        if improved:
            best_filters, best_error = found
        since_improved = 0 if improved else since_improved + 1

        if ((best_error <= PUBLISHED_ERROR_TARGET_DB and attempt >= MIN_RESTARTS)
                or since_improved >= STAGNATION_LIMIT):
            break

    if best_filters is None:
        raise RuntimeError(
            f"Filter optimization failed: none of the {attempt} restarts "
            "produced a converged, feasible solution.")
    return {
        'filters': best_filters,
        'error': best_error,
        'restarts': attempt,
        'target_met': best_error <= PUBLISHED_ERROR_TARGET_DB,
    }


def calculate_filters(comp):
    """Fit the published filter set for one compensation curve.

    Args:
        comp (Compensation): The listening level, mastering reference and scale.

    Returns:
        dict with 'filters' rounded to publication precision, the 'error' those
        published values actually achieve, the number of 'restarts' spent and
        whether 'target_met'.
    """
    fit = build_target(comp)
    gain_budget = GAIN_BUDGET_FACTOR * float(np.ptp(fit.target[fit.in_band]))

    _progress(f"Fitting listening level {_level_str(comp.level)} dB against a "
              f"{comp.reference:g} dB reference, scale {comp.scale:.2f}.")
    # No time estimate: this is a constrained minimax with multistart, and how
    # long it takes depends both on the machine and on how quickly the search
    # reaches its target. Elapsed time and restarts spent are reported after
    # the fact instead, which is true everywhere.
    _progress(f"  multistart to a {PUBLISHED_ERROR_TARGET_DB:g} dB published "
              f"target, up to {MAX_RESTARTS} restarts ...", end=" ")
    started = time.perf_counter()
    result = _fit_bands(BAND_TYPES, BAND_FC_BOUNDS, fit, gain_budget, seed=3)
    _progress(f"done ({time.perf_counter() - started:.1f} s, "
              f"{result['restarts']} restarts)")

    if not result['target_met']:
        _progress(f"  note: best published error {result['error']:.4f} dB does "
                  f"not reach the {PUBLISHED_ERROR_TARGET_DB:g} dB target. This "
                  f"is the best {BAND_COUNT} bands can do at this level; the "
                  "residual is still far below audibility.")
    return result


def headroom_adjustment(result):
    """Headroom for the published set, in 0.1 dB steps.

    Roon accepts one tenth of a dB, so the worst-case peak across all verified
    sample rates is rounded away from zero rather than to nearest: a listener
    who enters the published number must not clip at any of them.
    """
    peak = peak_gain(result['filters'])
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


def suggest_alternatives(comp):
    """Compute a scale and a listening level that would fit the 12 dB budget.

    Estimated from the size of the *target* curve rather than from the peak of
    the failed fit: when a fit succeeds its peak gain tracks the maximum of the
    target, whereas a fit that has run out of per-band gain overshoots, which
    would make both suggestions needlessly conservative.
    """
    budget = MAX_HEADROOM - SUGGESTION_MARGIN_DB
    peak_target = float(np.max(np.abs(ideal_delta(comp))))

    suggested_scale = None
    if peak_target > 0:
        raw = comp.scale * budget / peak_target
        suggested_scale = float(np.floor(raw * 20.0) / 20.0)
        suggested_scale = max(MIN_SCALE, min(MAX_SCALE, suggested_scale))
        if suggested_scale >= comp.scale:
            suggested_scale = None

    # Find the quietest listening level whose target still fits the budget.
    suggested_level = None
    already_fits = peak_target <= budget
    lo, hi = comp.level, min(comp.reference, MAX_LEVEL)
    reachable = float(np.max(np.abs(
        ideal_delta(replace(comp, level=hi))))) <= budget
    if not already_fits and reachable:
        for _ in range(60):
            mid = (lo + hi) / 2.0
            if float(np.max(np.abs(
                    ideal_delta(replace(comp, level=mid))))) > budget:
                lo = mid
            else:
                hi = mid
        # Bisection converges from above, so nudge before rounding up: without
        # this a level that already fits comes back one dB higher than itself.
        suggested_level = float(np.ceil(hi - 1e-6))
        if suggested_level <= comp.level:
            suggested_level = None
    return suggested_scale, suggested_level


def check_budget(result, comp):
    """Raise a ValueError with actionable suggestions if the set cannot be used."""
    peak = peak_gain(result['filters'])
    max_gain = max(abs(f[2]) for f in result['filters'])
    unreachable = result['error'] > FIT_ERROR_LIMIT_DB

    if peak <= MAX_HEADROOM and not unreachable:
        return

    reason = (
        f"the required headroom ({-peak:.2f} dB) exceeds the {MAX_HEADROOM:.1f} dB "
        f"available on Roon's Parametric EQ gain control"
        if peak > MAX_HEADROOM else
        f"the correction needs more than {MAX_BAND_GAIN:.0f} dB in a single band "
        f"(best achievable error {result['error']:.2f} dB)"
    )
    sug_scale, sug_level = suggest_alternatives(comp)
    lines = [
        f"Cannot build a usable filter set for --level {comp.level:g} "
        f"--reference {comp.reference:g}: {reason}.",
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
                 f"than {comp.reference:g} dB")
    raise ValueError("\n".join(lines))


# --- Output -----------------------------------------------------------------

def _level_str(level):
    return f"{int(level)}" if float(level).is_integer() else f"{level}"


def _scale_str(scale):
    """1.0 -> '1.0', 0.75 -> '0.75' -- never a bare integer, never trailing noise."""
    text = f"{scale:g}"
    return text if "." in text else f"{text}.0"


def preset_stem(comp):
    """Filename stem encoding what a preset actually is.

    A compensation curve is defined by the *pair* of levels, not by the
    listening level alone, so the reference belongs in the name. Scale is
    included so taste variants sit alongside each other without collision.
    """
    return (f"filter_{_level_str(comp.reference)}_to_{_level_str(comp.level)}"
            f"_s{_scale_str(comp.scale)}")


def _freq_str(fc):
    """Frequency at publication precision, with no trailing zeros.

    ``publication_round`` has already limited the significant figures, so this
    only has to render: 9885.0 prints as '9885', not '9885.0' or '9.885e+03'.
    A '%g' format would reach for exponential notation at 12 kHz, which is
    inside our range.
    """
    return f"{fc:.2f}".rstrip('0').rstrip('.')


def _filter_rows(filters):
    return [f"| {i} | {f[0]} | {_freq_str(f[1])} | {f[2]:.2f} | {f[3]:.2f} |"
            for i, f in enumerate(filters, 1)]


TABLE_HEAD = [
    "| Band | Type | Center Frequency (Hz) | Amplitude (dB) | Q-Value |",
    "| :--- | :--- | :--- | :--- | :--- |",
]


def is_null_correction(result):
    """True when every band rounds to zero at the host's entry precision.

    Happens when the listening level equals the mastering reference: the ideal
    correction is identically zero, and the honest output is a sentence rather
    than five bands of 0.00 dB. The preset still ships, because a listener at
    their reference level needs to be told to apply nothing -- without it they
    would reach for the nearest rung and apply a correction they do not need.
    """
    return all(abs(f[2]) < HOST_GAIN_PRECISION_DB / 2 for f in result['filters'])


def write_markdown_table(result, comp, headroom, filename):
    """Write the two-tier PEQ table."""
    if is_null_correction(result):
        content = "\n".join([
            f"### No Compensation Needed at {_level_str(comp.level)} dB",
            "",
            f"*Mastering reference {comp.reference:g} dB"
            + (" (default)" if comp.reference == DEFAULT_REFERENCE else "")
            + f" · listening level {_level_str(comp.level)} dB · scale {comp.scale:.2f}*",
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
        f"### Equal-Loudness Compensation EQ for {_level_str(comp.level)} dB",
        "",
        f"*Mastering reference {comp.reference:g} dB"
        + (" (default)" if comp.reference == DEFAULT_REFERENCE else "")
        + f" · listening level {_level_str(comp.level)} dB"
        + f" · scale {comp.scale:.2f} · designed at {DESIGN_FS / 1000:.1f} kHz*",
        "",
        f"**Headroom adjustment: {headroom:.1f} dB.** Apply this as a negative "
        "preamp / headroom setting. It is the worst case across "
        f"{'/'.join(f'{r / 1000:g}' for r in VERIFY_RATES)} kHz.",
        "",
        f"#### {BAND_COUNT} bands (max residual error {result['error']:.4f} dB)",
        "",
        "A complete full-spectrum correction. The residual error is the deviation "
        "these published, rounded values leave against the ideal ISO 226 target — "
        "it is quoted for the numbers below, not for an unrounded fit behind them.",
        "",
    ]
    lines += TABLE_HEAD + _filter_rows(result['filters']) + [""]

    content = "\n".join(lines)
    with open(filename, 'w', encoding='utf-8') as handle:
        handle.write(content)
    print(content)
    print(f"Saved PEQ table to: {filename}")


def write_camilladsp_yaml(result, comp, headroom, filename):
    """Write the band set as a CamillaDSP YAML file for direct REW import."""
    type_map = {LOW_SHELF: 'Lowshelf', HIGH_SHELF: 'Highshelf', PEAK: 'Peaking'}
    filters = {}
    for i, (ftype, fc, gain, q_val) in enumerate(result['filters'], 1):
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
            f"# No compensation needed at {_level_str(comp.level)} dB.",
            f"# Listening level equals the mastering reference "
            f"({comp.reference:g} dB), so the ideal correction is 0.00 dB at every",
            "# frequency. Apply no filters and no headroom adjustment.",
            "# The bands below are all zero-gain and are included only so this",
            "# file is a valid, loadable CamillaDSP configuration.",
            "",
        ]
    else:
        header = [
            f"# Equal-Loudness Compensation EQ for {_level_str(comp.level)} dB",
            f"# Mastering reference: {comp.reference:g} dB"
            + ("  (default)" if comp.reference == DEFAULT_REFERENCE else "")
            + f" · listening level: {_level_str(comp.level)} dB · scale: {comp.scale:.2f}",
            f"# Headroom adjustment: {headroom:.1f} dB "
            f"(apply as negative preamp gain)",
            f"# Designed at {DESIGN_FS / 1000:.1f} kHz.",
            f"# {BAND_COUNT} bands, max residual error "
            f"{result['error']:.4f} dB against the ideal ISO 226 target.",
            "",
        ]
    body = yaml.dump({'filters': filters}, sort_keys=False, default_flow_style=False)
    with open(filename, 'w', encoding='utf-8') as handle:
        handle.write("\n".join(header) + body)
    print(f"Saved CamillaDSP YAML file to: {filename}")


def plot_frequency_response(result, comp, headroom, filename):
    """Plot the published response against the ideal target."""
    # Imported lazily and deliberately: matplotlib costs about a second to
    # import, and nothing else in this module needs it. Hoisting it to the top
    # would slow every CLI invocation, including the ones that only print a
    # table or fail validation.
    # pylint: disable=import-outside-toplevel
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    freqs = np.logspace(np.log10(20), np.log10(20000), 2000)
    response = get_filter_response(result['filters'], freqs) + headroom
    target = np.interp(np.log10(freqs), np.log10(ISO_FREQ),
                       ideal_delta(comp)) + headroom

    plt.figure(figsize=(12, 6))
    plt.semilogx(freqs, target, color='#7f7f7f', linewidth=3, alpha=0.45,
                 label='Ideal ISO 226 target')
    plt.semilogx(freqs, response, color='#1f77b4', linewidth=2,
                 label=f"{BAND_COUNT} bands as published "
                       f"(max error {result['error']:.4f} dB)")

    plt.axhline(0, color='#d62728', linestyle='--', linewidth=1.2,
                label='Digital clipping limit (0 dB)')
    plt.axhline(headroom, color='black', linestyle=':', linewidth=1,
                label=f'Flat reference ({headroom:.1f} dB)')
    plt.axvspan(12500, 20000, color='#999999', alpha=0.12,
                label='Beyond ISO 226 data (extrapolated)')

    plt.title(
        f'Equal-Loudness PEQ Compensation — listening at {_level_str(comp.level)} dB, '
        f'mastered for {comp.reference:g} dB'
        + (' (default)' if comp.reference == DEFAULT_REFERENCE else '')
        + (f', scale {comp.scale:.2f}' if comp.scale != 1.0 else '') + '\n'
        f'Headroom adjustment {headroom:.1f} dB · designed at '
        f'{DESIGN_FS / 1000:.1f} kHz'
    )
    plt.xlabel('Frequency (Hz)')
    plt.ylabel('Amplitude (dB)')
    plt.grid(True, which='both', linestyle='--', alpha=0.5)
    plt.xlim([20, 20000])
    lo = min(np.min(response), headroom) - 1
    plt.ylim([min(lo, -6), max(np.max(response) + 1, 2)])
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
    parser.add_argument('--scale', type=float, default=DEFAULT_SCALE,
                        help=f'Fraction of the theoretical correction to apply '
                             f'(default: {DEFAULT_SCALE:g}, range: '
                             f'{MIN_SCALE}-{MAX_SCALE})')
    args = parser.parse_args()

    try:
        comp = Compensation(args.level, args.reference, args.scale)
        result = calculate_filters(comp)
        check_budget(result, comp)
    except ValueError as err:
        print(f"Error: {err}", file=sys.stderr)
        return 1

    headroom = headroom_adjustment(result)
    diag = cascade_diagnostics(result['filters'])
    print(f"Cascade conditioning: final peak {diag['final_peak']:+.2f} dB, "
          f"worst intermediate stage {diag['stage_peak']:+.2f} dB, "
          f"total |gain| {diag['gain_sum']:.2f} dB, "
          f"quantization sensitivity {diag['quantization_sensitivity']:.4f} dB, "
          f"opposing neighbours {diag['opposing_neighbours']:.2f} dB/octave")

    stem = preset_stem(comp)
    write_markdown_table(result, comp, headroom, f"{stem}.md")
    write_camilladsp_yaml(result, comp, headroom, f"{stem}.yml")
    plot_frequency_response(result, comp, headroom, f"{stem}.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
