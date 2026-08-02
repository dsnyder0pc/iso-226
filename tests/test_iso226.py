"""
Regression tests for the ISO 226 implementation and the filter design.

The important one is `test_matches_published_annex_b`: it checks Formula (1)
against values published in ISO 226:2023 Annex B rather than against anything
this repository computes. Every other check in the project shares `iso226_spl`
and `get_filter_response`, so without an external reference the verification
would be circular.
"""

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from iso226_utils import (  # noqa: E402
    ANNEX_B_TOLERANCE_DB, ISO226_PHON_MAX, ISO226_PHON_MIN, ISO_FREQ,
    REF_1KHZ_INDEX, VERIFY_RATES, get_filter_response, ideal_delta,
    iso226_spl, peak_gain,
)


# --- ISO 226 Formula (1) ---------------------------------------------------

def test_matches_published_annex_b(annex_b_40_phon):
    """Formula (1) must reproduce the 40 phon contour of ISO 226:2023 Annex B.

    Table B.1 is printed to 0.1 dB, so agreement within 0.05 dB is exact to the
    precision the standard publishes. This is the only assertion in the suite
    whose expected values come from outside this repository -- which is exactly
    why it is worth having, and why it skips rather than shipping ISO's data.
    """
    computed = iso226_spl(40.0, ISO_FREQ)
    assert np.max(np.abs(computed - annex_b_40_phon)) <= ANNEX_B_TOLERANCE_DB


def test_1khz_is_identity():
    """By definition, a contour at L phon passes through L dB SPL at 1 kHz."""
    for phon in (20.0, 40.0, 60.0, 83.0):
        assert abs(iso226_spl(phon, ISO_FREQ)[REF_1KHZ_INDEX] - phon) < 0.15


def test_rejects_levels_outside_the_standard():
    """ISO 226:2023 s4.1 defines Formula (1) only from 20 to 90 phon."""
    for phon in (ISO226_PHON_MIN - 0.1, ISO226_PHON_MAX + 0.1, 0.0, 120.0):
        with pytest.raises(ValueError):
            iso226_spl(phon)


def test_coefficients_interpolate_in_log_frequency():
    """Between tabulated points the result must sit between its neighbours."""
    lower = iso226_spl(60.0, np.array([1000.0]))[0]
    upper = iso226_spl(60.0, np.array([1250.0]))[0]
    mid = iso226_spl(60.0, np.array([float(np.sqrt(1000.0 * 1250.0))]))[0]
    assert min(lower, upper) <= mid <= max(lower, upper)


# --- The compensation target ------------------------------------------------

def test_target_is_zero_at_1khz():
    """Every compensation curve is normalized to 0 dB at 1 kHz."""
    assert abs(ideal_delta(65.0, 83.0)[REF_1KHZ_INDEX]) < 1e-9


def test_target_vanishes_when_level_equals_reference():
    assert np.max(np.abs(ideal_delta(83.0, 83.0))) < 1e-9


def test_target_boosts_bass_below_reference_and_cuts_above():
    """Below the mastering level bass needs lifting; above it, trimming."""
    assert ideal_delta(65.0, 83.0)[0] > 0
    assert ideal_delta(88.0, 83.0)[0] < 0


def test_scale_is_linear():
    full = ideal_delta(65.0, 83.0)
    half = ideal_delta(65.0, 83.0, scale=0.5)
    assert np.allclose(half, full * 0.5)


def test_measurement_convention_offset_cancels():
    """A shared offset between --level and --reference must not matter much.

    Both are broadband C-weighted readings rather than the loudness level of an
    equally loud 1 kHz tone. Because the target is a *difference* of contours,
    an offset common to both cancels to first order -- which is what lets a
    listener use an ordinary SPL meter instead of a calibrated tone.
    """
    base = ideal_delta(65.0, 83.0)
    for offset in (2.0, 4.0, 6.0, 7.0):
        shifted = ideal_delta(65.0 + offset, 83.0 + offset)
        assert np.max(np.abs(shifted - base)) < 0.1


def test_level_error_matters_far_more_than_convention():
    """Mis-measuring the level is the dominant error source, by ~50x."""
    base = ideal_delta(65.0, 83.0)
    convention = np.max(np.abs(ideal_delta(71.0, 89.0) - base))
    level = np.max(np.abs(ideal_delta(71.0, 83.0) - base))
    assert level > 20 * convention


# --- Biquads ----------------------------------------------------------------

def test_zero_gain_is_transparent():
    freqs = np.logspace(np.log10(20), np.log10(20000), 64)
    resp = get_filter_response([('Peak', 1000.0, 0.0, 1.0)], freqs)
    assert np.max(np.abs(resp)) < 1e-9


def test_low_shelf_approaches_its_gain_at_dc():
    resp = get_filter_response([('Low Shelf', 100.0, 6.0, 0.7)],
                               np.array([1.0]))[0]
    assert abs(resp - 6.0) < 0.1


def test_low_shelf_passband_is_flat():
    resp = get_filter_response([('Low Shelf', 100.0, 6.0, 0.7)],
                               np.array([15000.0]))[0]
    assert abs(resp) < 0.05


@pytest.mark.parametrize('fs', VERIFY_RATES)
@pytest.mark.parametrize('gain', [-6.0, -0.41, 3.0, 8.0])
def test_high_shelf_passband_is_flat_at_every_rate(fs, gain):
    """A high shelf must be 0 dB well below its corner, at any sample rate.

    This is the regression test for a sign error in the b2 coefficient of the
    RBJ high-shelf formula. The faulty term scaled with cos(w0), so it was
    nearly invisible for a 10 kHz shelf at 44.1 kHz (0.009 dB) but reached
    1.51 dB at 192 kHz -- a -0.41 dB shelf that produced a +1.5 dB boost.
    """
    resp = get_filter_response([('High Shelf', 10000.0, gain, 0.78)],
                               np.array([100.0, 500.0]), fs)
    assert np.max(np.abs(resp)) < 0.05


@pytest.mark.parametrize('fs', VERIFY_RATES)
def test_high_shelf_reaches_its_gain_above_the_corner(fs):
    resp = get_filter_response([('High Shelf', 2000.0, 6.0, 0.7)],
                               np.array([fs / 2.0 * 0.98]), fs)[0]
    assert abs(resp - 6.0) < 0.3


def test_shelves_never_overshoot_their_own_gain():
    """A cut must never produce a boost anywhere, and vice versa."""
    grid = np.logspace(np.log10(10), np.log10(20000), 2000)
    for fs in VERIFY_RATES:
        for ftype, fc in (('High Shelf', 10000.0), ('Low Shelf', 60.0)):
            cut = get_filter_response([(ftype, fc, -3.0, 0.78)], grid, fs)
            assert np.max(cut) < 0.05
            boost = get_filter_response([(ftype, fc, 3.0, 0.78)], grid, fs)
            assert np.min(boost) > -0.05


def test_cascade_is_additive_in_db():
    freqs = np.logspace(np.log10(20), np.log10(20000), 64)
    a = ('Peak', 200.0, 3.0, 1.0)
    b = ('High Shelf', 8000.0, -2.0, 0.7)
    combined = get_filter_response([a, b], freqs)
    separate = get_filter_response([a], freqs) + get_filter_response([b], freqs)
    assert np.allclose(combined, separate, atol=1e-9)


def test_unknown_filter_type_is_rejected():
    with pytest.raises(ValueError):
        get_filter_response([('Notch', 1000.0, 3.0, 1.0)], np.array([1000.0]))


def test_cascade_diagnostics_flag_a_cancelling_pair():
    """The conditioning metrics must actually detect the degenerate case.

    Two large opposing filters at nearly the same frequency measure fine
    end-to-end but overflow intermediate nodes in serial fixed-point DSPs and
    lose their cancellation under host coefficient quantization.
    """
    import importlib.util
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    spec = importlib.util.spec_from_file_location(
        "lf", os.path.join(here, "loudness-filters.py"))
    lf = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lf)

    healthy = [('Low Shelf', 77.5, 10.39, 0.42), ('Peak', 321.0, 2.39, 0.25),
               ('Peak', 771.1, -1.78, 0.36), ('Peak', 5482.0, -0.62, 0.59),
               ('High Shelf', 10921.3, 4.45, 0.68)]
    degenerate = [('Low Shelf', 77.5, 10.39, 0.42), ('Peak', 450.0, 17.33, 0.25),
                  ('Peak', 477.1, -16.12, 0.26), ('Peak', 5482.0, -0.62, 0.59),
                  ('High Shelf', 10921.3, 4.45, 0.68)]

    good = lf.cascade_diagnostics(healthy)
    bad = lf.cascade_diagnostics(degenerate)

    assert bad['opposing_neighbours'] > 10 * good['opposing_neighbours']
    assert bad['quantization_sensitivity'] > good['quantization_sensitivity']
    # The boosting section runs far hotter than the end-to-end response shows.
    assert bad['stage_peak'] - bad['final_peak'] > 5.0
    assert good['stage_peak'] - good['final_peak'] < 0.5


def test_peak_gain_covers_every_verified_rate():
    filters = [('High Shelf', 10000.0, 4.0, 0.7)]
    worst = peak_gain(filters)
    grid = np.logspace(np.log10(20), np.log10(20000), 500)
    for rate in VERIFY_RATES:
        assert np.max(get_filter_response(filters, grid, rate)) <= worst + 1e-9
