"""
ISO 226 equal-loudness contours, target-curve construction, and biquad helpers.

Equal-loudness data and Formula (1) are from ISO 226:2023 (third edition),
which supersedes ISO 226:2003. The third edition revised Formula (1) itself and
every alpha_f in Table 1; the two editions are not interchangeable.
"""

import importlib.util
import os
from dataclasses import dataclass
from typing import NamedTuple

import numpy as np
from scipy.signal import freqz

# ---------------------------------------------------------------------------
# ISO 266 preferred third-octave frequencies. These index Table 1 and are the
# R10 preferred-number series; they are kept here because they are needed to
# align the coefficients that are not.
# ---------------------------------------------------------------------------
ISO_FREQ = np.array([
    20.0, 25.0, 31.5, 40.0, 50.0, 63.0, 80.0, 100.0, 125.0, 160.0, 200.0,
    250.0, 315.0, 400.0, 500.0, 630.0, 800.0, 1000.0, 1250.0, 1600.0,
    2000.0, 2500.0, 3150.0, 4000.0, 5000.0, 6300.0, 8000.0, 10000.0, 12500.0
])

# Index of 1000 Hz in ISO_FREQ: every curve here is normalized to 0 dB there.
REF_1KHZ_INDEX = 17

# ---------------------------------------------------------------------------
# ISO 226:2023 Table 1 — per-frequency coefficients for Formula (1).
#
# These belong to ISO and are not redistributable, so they are not committed.
# Supply them from your own copy of the standard: see NOTICE and the template
# at tests/iso226_table1.py.example. Unlike the Annex B fixture, which only
# disables one test, nothing in this project evaluates without these.
# ---------------------------------------------------------------------------
TABLE1_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "reference", "iso226_table1.py")

_TABLE1_MISSING = f"""ISO 226:2023 Table 1 coefficients not found.

Expected: {TABLE1_PATH}

These are the per-frequency coefficients of ISO 226 Formula (1). They belong to
ISO and cannot be redistributed, so this repository does not carry them.

  1. Copy tests/iso226_table1.py.example to reference/iso226_table1.py
  2. Fill in the three columns of Table 1 from your own copy of the standard
     (https://www.iso.org/standard/83117.html)

The presets already in PEQ/ and REW/ were generated with these coefficients and remain
usable without this file; only regenerating them or building new listening
levels needs it."""


def _load_table1():
    """Load Table 1 from reference/, checking its shape but not its values.

    The only content check is structural: L_U is specified *relative to 1 kHz*,
    so its 1 kHz entry is 0.0 by definition rather than by measurement. Testing
    it catches an off-by-one during transcription -- the likeliest mistake --
    without this file asserting any value that belongs to ISO.
    """
    if not os.path.exists(TABLE1_PATH):
        raise ImportError(_TABLE1_MISSING)

    spec = importlib.util.spec_from_file_location("iso226_table1", TABLE1_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def column(name):
        values = getattr(module, name, None)
        if not values:
            raise ImportError(
                f"{TABLE1_PATH} defines no {name}, or leaves it empty. "
                f"See tests/iso226_table1.py.example.")
        found = np.asarray(values, dtype=float)
        if found.shape != ISO_FREQ.shape:
            raise ImportError(
                f"{TABLE1_PATH}: {name} has {found.size} values, expected "
                f"{ISO_FREQ.size} -- one per ISO 266 preferred frequency from "
                f"20 Hz to 12.5 kHz.")
        return found

    alpha_f, l_u, t_f = column("ISO_AF"), column("ISO_LU"), column("ISO_TF")
    if l_u[REF_1KHZ_INDEX] != 0.0:
        raise ImportError(
            f"{TABLE1_PATH}: ISO_LU at 1 kHz (index {REF_1KHZ_INDEX}) is "
            f"{l_u[REF_1KHZ_INDEX]}, but L_U is defined relative to 1 kHz and "
            "must be 0.0 there. The columns are probably misaligned.")
    return alpha_f, l_u, t_f


ISO_AF, ISO_LU, ISO_TF = _load_table1()

# Reference-tone quantities in Formula (1). The first two are the 1 kHz entries
# of Table 1, derived rather than restated so there is one source for each. The
# 1 kHz exponent moving from 0.25 (2003) to 0.30 is the change that shifted the
# whole coefficient set.
ALPHA_R = float(ISO_AF[REF_1KHZ_INDEX])   # loudness exponent at 1 kHz
T_R = float(ISO_TF[REF_1KHZ_INDEX])       # threshold of hearing at 1 kHz, dB
P0_OVER_PA_SQ = 4e-10                     # (p0/pa)^2, p0 = 20 uPa, pa = 1 Pa

# ISO 226:2023 s4.1 states Formula (1) applies from a lower limit of 20 phon
# up to 90 phon (20 Hz - 4 kHz) and 80 phon (5 kHz - 12.5 kHz).
ISO226_PHON_MIN = 20.0
ISO226_PHON_MAX = 90.0
ISO226_PHON_MAX_HF = 80.0
ISO226_HF_LIMIT_HZ = 5000.0

# Tolerance for the Annex B regression check. ISO 226:2023 Table B.1 is printed
# to 0.1 dB, so agreement within 0.05 dB is exact to the precision the standard
# publishes. The contour values themselves are ISO's and are not redistributable;
# they live in the gitignored reference/annex_b_2023.py -- see
# tests/annex_b_reference.py.example.
ANNEX_B_TOLERANCE_DB = 0.05

# ---------------------------------------------------------------------------
# Design constants
# ---------------------------------------------------------------------------
# Filters are designed and analysed at 44.1 kHz: it is still the most common
# rate for digital music, and biquad frequency warping near Nyquist makes it
# the least forgiving of the common rates for a high-frequency shelf.
DESIGN_FS = 44100.0

# Headroom is verified across all of these; the worst case is published.
VERIFY_RATES = (44100.0, 48000.0, 96000.0, 192000.0)

# The ISO data stops at 12.5 kHz and 20 Hz. Outside that range the target is
# held flat at the edge value, and the fit is constrained (but not optimized)
# there, so the extrapolation is bounded and deliberate rather than accidental.
EXTRAP_LOW_HZ = 10.0
EXTRAP_HIGH_HZ = 20000.0
EXTRAP_TOLERANCE_DB = 1.5

# ---------------------------------------------------------------------------
# What defines one preset
# ---------------------------------------------------------------------------
# The compensation curve is a property of the *pair* of levels, not of either
# alone, and `scale` is the fraction of it applied. These three travel together
# through everything -- target construction, fitting, refusal messages,
# filenames, all three writers -- so they are one value rather than three
# parameters repeated in a fixed order.
DEFAULT_REFERENCE = 83.0
DEFAULT_SCALE = 1.0

MIN_LEVEL, MAX_LEVEL = 50.0, 90.0
MIN_REFERENCE, MAX_REFERENCE = 70.0, 90.0
MIN_SCALE, MAX_SCALE = 0.1, 1.0


@dataclass(frozen=True)
class Compensation:
    """A validated (level, reference, scale) triple: one compensation curve.

    ``level`` is *measured* in the room, broadband and C-weighted.
    ``reference`` is a property of the *recording* -- the level it was mastered
    to sound correct at. They are not interchangeable, and passing one where the
    other belongs is the mistake this type exists to make hard.

    Frozen, and validated once at construction, so nothing downstream has to
    re-check a range or worry about a caller mutating it mid-fit.
    """

    level: float
    reference: float = DEFAULT_REFERENCE
    scale: float = DEFAULT_SCALE

    def __post_init__(self):
        if not MIN_LEVEL <= self.level <= MAX_LEVEL:
            raise ValueError(
                f"Target listening level ({self.level} dB) must be between "
                f"{MIN_LEVEL} and {MAX_LEVEL} dB SPL.")
        if not MIN_REFERENCE <= self.reference <= MAX_REFERENCE:
            raise ValueError(
                f"Reference (mastering) level ({self.reference} dB) must be "
                f"between {MIN_REFERENCE} and {MAX_REFERENCE} dB SPL.")
        if not MIN_SCALE <= self.scale <= MAX_SCALE:
            raise ValueError(
                f"Scale ({self.scale}) must be between {MIN_SCALE} and "
                f"{MAX_SCALE}.")

    @property
    def is_null(self):
        """True when the listener is already at the mastering reference."""
        return self.level == self.reference


class FitTarget(NamedTuple):
    """The design grid, the target on it, and the ISO-backed span to fit over.

    A NamedTuple rather than a dataclass so the three can still be unpacked
    positionally where that reads better than attribute access.
    """

    grid: np.ndarray
    target: np.ndarray
    in_band: slice


def iso226_spl(phon, f_arr=None):
    """Sound pressure level (dB SPL) for a given loudness level, per ISO 226.

    Implements ISO 226:2023 Formula (1). Coefficients are interpolated in
    log-frequency (the axis they are tabulated on) when ``f_arr`` falls between
    the standard preferred frequencies.

    Args:
        phon (float): Loudness level in phon. ISO 226:2023 s4.1 defines
            Formula (1) from 20 phon up to 90 phon (20 Hz - 4 kHz) and
            80 phon (5 kHz - 12.5 kHz).
        f_arr (np.ndarray): Frequencies to evaluate. Defaults to ISO_FREQ.

    Returns:
        np.ndarray: Sound pressure level in dB SPL.
    """
    if phon < ISO226_PHON_MIN or phon > ISO226_PHON_MAX:
        raise ValueError(
            f"Loudness level ({phon} phon) is outside the range for which "
            f"ISO 226:2023 Formula (1) is defined "
            f"({ISO226_PHON_MIN:.0f} to {ISO226_PHON_MAX:.0f} phon)."
        )
    if f_arr is None:
        f_arr = ISO_FREQ

    log_f = np.log10(np.asarray(f_arr, dtype=float))
    log_iso = np.log10(ISO_FREQ)
    af = np.interp(log_f, log_iso, ISO_AF)
    lu = np.interp(log_f, log_iso, ISO_LU)
    tf = np.interp(log_f, log_iso, ISO_TF)

    # ISO 226:2023 Formula (1).
    #
    # The bracketed difference is the loudness of the 1 kHz reference tone above
    # its own threshold; the trailing term is the threshold at frequency f. Both
    # loudness terms at frequency f carry alpha_f, while the reference bracket
    # carries alpha_r -- equating the two is what defines an equal-loudness
    # contour. The (p0/pa)^(2(alpha_r - alpha_f)) factor reconciles the differing
    # exponents, and is unity at 1 kHz where alpha_f == alpha_r.
    a_f = (P0_OVER_PA_SQ ** (ALPHA_R - af)
           * (10 ** (0.1 * ALPHA_R * phon) - 10 ** (0.1 * ALPHA_R * T_R))
           + 10 ** (0.1 * af * (tf + lu)))
    return (10.0 / af) * np.log10(a_f) - lu


def ideal_delta(comp):
    """The equal-loudness compensation target at the ISO preferred frequencies.

    The difference in contour *shape* between the listening level and the
    mastering (reference) level, normalized to 0 dB at 1 kHz.

    Because this is a difference of two contours, a systematic offset shared by
    both levels -- such as reading broadband C-weighted SPL rather than the
    loudness level of an equally loud 1 kHz tone -- cancels to first order.
    What matters is that the two levels are measured the same way.

    Args:
        comp (Compensation): The listening level, mastering reference and scale.

    Returns:
        np.ndarray: Target gain in dB at each ISO_FREQ.
    """
    target_spl = iso226_spl(comp.level)
    ref_spl = iso226_spl(comp.reference)
    delta = ((target_spl - target_spl[REF_1KHZ_INDEX])
             - (ref_spl - ref_spl[REF_1KHZ_INDEX]))
    return delta * comp.scale


def design_grid():
    """Frequency grid used for filter fitting.

    Returns three arrays: the sub-20 Hz extrapolation region, the ISO-backed
    region that the minimax objective actually minimizes over, and the
    above-12.5 kHz extrapolation region.
    """
    low = np.logspace(np.log10(EXTRAP_LOW_HZ), np.log10(19.5), 12)
    in_band = np.logspace(np.log10(ISO_FREQ[0]), np.log10(ISO_FREQ[-1]), 150)
    high = np.logspace(np.log10(12800.0), np.log10(EXTRAP_HIGH_HZ), 20)
    return low, in_band, high


def build_target(comp):
    """Fit target over the full design grid, with flat-held extrapolation.

    Args:
        comp (Compensation): The listening level, mastering reference and scale.

    Returns:
        FitTarget: ``grid``, ``target`` and the ``in_band`` slice selecting the
        ISO-backed portion that the minimax objective minimizes over. It is a
        NamedTuple, so ``grid, target, in_band = build_target(comp)`` still
        works where the three are wanted separately.
    """
    low, in_band, high = design_grid()
    delta = ideal_delta(comp)
    t_low = np.full(len(low), delta[0])
    t_in = np.interp(np.log10(in_band), np.log10(ISO_FREQ), delta)
    t_high = np.full(len(high), delta[-1])
    return FitTarget(
        grid=np.concatenate([low, in_band, high]),
        target=np.concatenate([t_low, t_in, t_high]),
        in_band=slice(len(low), len(low) + len(in_band)),
    )


def get_biquad_coefs(ftype, fc, fs, gain, q):
    """Biquad coefficients per Robert Bristow-Johnson's Audio EQ Cookbook.

    Args:
        ftype (str): One of 'Peak', 'Low Shelf', or 'High Shelf'.
        fc (float): Centre or corner frequency in Hz.
        fs (float): Sampling frequency in Hz.
        gain (float): Gain in dB.
        q (float): Q-factor.

    Returns:
        tuple: feedforward (b) and feedback (a) coefficient lists.
    """
    if gain == 0:
        return [1.0, 0.0, 0.0], [1.0, 0.0, 0.0]

    a_val = 10 ** (gain / 40.0)
    w0 = 2 * np.pi * fc / fs
    alpha = np.sin(w0) / (2 * q)

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
        b2 = a_val * ((a_val + 1) + (a_val - 1) * np.cos(w0) - 2 * np.sqrt(a_val) * alpha)
        a0 = (a_val + 1) - (a_val - 1) * np.cos(w0) + 2 * np.sqrt(a_val) * alpha
        a1 = 2 * ((a_val - 1) - (a_val + 1) * np.cos(w0))
        a2 = (a_val + 1) - (a_val - 1) * np.cos(w0) - 2 * np.sqrt(a_val) * alpha
    else:
        raise ValueError(f"Unsupported filter type: {ftype}")

    return [b0 / a0, b1 / a0, b2 / a0], [1.0, a1 / a0, a2 / a0]


def get_filter_response(filters, frequencies, fs=DESIGN_FS):
    """Combined magnitude response in dB of a cascade of filters.

    Args:
        filters (list): Tuples of (ftype, fc, gain, q).
        frequencies (np.ndarray): Frequencies to evaluate at.
        fs (float): Sampling frequency in Hz. Defaults to DESIGN_FS (44.1 kHz).

    Returns:
        np.ndarray: Response in dB.
    """
    frequencies = np.asarray(frequencies, dtype=float)
    w_eval = 2 * np.pi * frequencies / fs
    total_h = np.ones(len(frequencies), dtype=complex)
    for filt in filters:
        b, a = get_biquad_coefs(filt[0], filt[1], fs, filt[2], filt[3])
        _, h = freqz(b, a, worN=w_eval)
        total_h *= h
    return 20 * np.log10(np.abs(total_h))


def peak_gain(filters, rates=VERIFY_RATES):
    """Worst-case peak gain (dB) of a filter cascade across sample rates.

    Biquad responses warp near Nyquist, so a shelf near the top of the audio
    band realizes a different gain at 44.1 kHz than at 192 kHz. The published
    headroom figure must cover the worst of them.
    """
    grid = np.logspace(np.log10(20.0), np.log10(20000.0), 3000)
    return max(float(np.max(get_filter_response(filters, grid, fs)))
               for fs in rates)


# --- Level matching ---------------------------------------------------------
# A compensation curve boosts the extremes and leaves 1 kHz alone, so a preset
# and its own bypass need not play at the same apparent level even on an
# identical preamp. Comparing them as-is risks comparing volume, and the louder
# of two similar presentations is reliably preferred -- which would credit the
# filters with work they are not doing. This function sizes that difference so
# it can be taken out of the comparison.
#
# The measure is the cascade's own gain at MATCH_FREQ_HZ, the normalization
# frequency -- the one point the whole project defines the compensation to be
# 0 dB at. Matching there says only that the two sides of an A/B should have
# identical *midrange*, and lets the restored bass and treble be the entire
# audible difference.
#
# That is deliberately the weakest claim available. Stronger ones have been
# tried and withdrawn after listening: any measure that weighs the restored
# extremes -- BS.1770, a C-weighted meter, an ISO 226-weighted integral, or a
# match below the midrange -- over-credits the bass relative to what the ear
# does at these levels, and gives the flat side a level advantage that decides
# the comparison before tonal balance gets a say. See the bypass invariant in
# CLAUDE.md if you are about to re-derive one of them.
#
# Note this does not read exactly zero. It is the *cascade's* gain, not the
# target's, so it picks up however far five bands miss 0 dB at 1 kHz: under
# 0.07 dB everywhere except 83->60, the loosest preset in the set, at
# -0.205 dB. That is not error leaking in -- if the compensated side really
# does play 0.2 dB quiet at 1 kHz, matching there means attenuating the flat
# side to meet it.
MATCH_FREQ_HZ = float(ISO_FREQ[REF_1KHZ_INDEX])

# Below this, the bypass and the headroom are the same setting to a listener,
# so callers publish one number instead of two near-identical ones. Level
# differences under about 0.2 dB are not reliably discriminable.
MATCH_NEGLIGIBLE_DB = 0.2


def match_delta(filters):
    """How much louder a cascade plays than its own bypass, in dB.

    The cascade's gain at MATCH_FREQ_HZ, the normalization frequency. Since
    the compensation is defined to be 0 dB there, this is small by
    construction -- it is whatever is left of the fit's own miss at 1 kHz --
    and `bypass_headroom` collapses it onto the headroom below
    MATCH_NEGLIGIBLE_DB, which is almost everywhere.

    Read from the published filters rather than the ideal target, because
    those are what a listener actually plays: matching a listener's A/B
    against a curve nobody can load would be matching the wrong thing.

    Both sides carry the same preamp, so the preamp cancels and only the
    bands are measured.
    """
    if not filters:
        return 0.0
    return float(get_filter_response(filters, np.array([MATCH_FREQ_HZ]))[0])
