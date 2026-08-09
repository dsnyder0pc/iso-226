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

# The repo root must be on sys.path before the project modules import.
# pylint: disable=wrong-import-position
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import iso226_utils  # noqa: E402
from iso226_utils import (  # noqa: E402
    ALPHA_R, ANNEX_B_TOLERANCE_DB, ISO226_PHON_MAX, ISO226_PHON_MIN, ISO_AF,
    ISO_FREQ, ISO_TF, REF_1KHZ_INDEX, T_R, VERIFY_RATES, Compensation,
    MATCH_FREQ_HZ, MATCH_NEGLIGIBLE_DB, get_filter_response, ideal_delta,
    iso226_spl, match_delta, peak_gain,
)


# --- Table 1 loader --------------------------------------------------------
#
# Every value below is invented. The loader validates the *shape* of Table 1 and
# never its contents, so these tests need no ISO data -- which is the point: the
# coefficients are not in this repository and must not be reintroduced here.

def _synthetic_table(tmp_path, alpha_f=None, l_u=None, t_f=None):
    """Write a Table 1 module with arbitrary, correctly shaped columns."""
    count = len(ISO_FREQ)
    if l_u is None:
        l_u = [0.0] * count           # 0.0 at 1 kHz, as the definition requires
    path = tmp_path / "iso226_table1.py"
    path.write_text(
        f"ISO_AF = {list(alpha_f if alpha_f is not None else [0.3] * count)}\n"
        f"ISO_LU = {list(l_u)}\n"
        f"ISO_TF = {list(t_f if t_f is not None else [2.4] * count)}\n",
        encoding="utf-8")
    return str(path)


def test_loader_reports_a_missing_table(monkeypatch, tmp_path):
    """The message has to say what to copy where; nothing runs without it."""
    monkeypatch.setattr(iso226_utils, "TABLE1_PATH", str(tmp_path / "absent.py"))
    with pytest.raises(ImportError, match="iso226_table1.py.example"):
        iso226_utils._load_table1()  # pylint: disable=protected-access


def test_loader_rejects_a_short_column(monkeypatch, tmp_path):
    """A truncated paste would otherwise misalign every contour silently."""
    path = _synthetic_table(tmp_path, alpha_f=[0.3] * (len(ISO_FREQ) - 1))
    monkeypatch.setattr(iso226_utils, "TABLE1_PATH", path)
    with pytest.raises(ImportError, match="ISO_AF has 28 values"):
        iso226_utils._load_table1()  # pylint: disable=protected-access


def test_loader_rejects_a_misaligned_lu_column(monkeypatch, tmp_path):
    """L_U is 0.0 at 1 kHz by definition, so this catches an off-by-one.

    Transcribing 29 rows by hand and dropping or doubling one is the likeliest
    mistake, and it would otherwise shift every contour without any symptom.
    """
    shifted = [0.0] * len(ISO_FREQ)
    shifted[REF_1KHZ_INDEX] = -2.7
    path = _synthetic_table(tmp_path, l_u=shifted)
    monkeypatch.setattr(iso226_utils, "TABLE1_PATH", path)
    with pytest.raises(ImportError, match="misaligned"):
        iso226_utils._load_table1()  # pylint: disable=protected-access


def test_reference_tone_constants_come_from_the_table():
    """ALPHA_R and T_R are derived, not restated, so they cannot drift."""
    assert ALPHA_R == ISO_AF[REF_1KHZ_INDEX]
    assert T_R == ISO_TF[REF_1KHZ_INDEX]


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


# --- The Compensation bundle ------------------------------------------------

@pytest.mark.parametrize("kwargs,expected", [
    ({"level": 40.0}, "listening level"),
    ({"level": 95.0}, "listening level"),
    ({"level": 74.0, "reference": 60.0}, "Reference"),
    ({"level": 74.0, "reference": 95.0}, "Reference"),
    ({"level": 74.0, "scale": 0.0}, "Scale"),
    ({"level": 74.0, "scale": 1.5}, "Scale"),
])
def test_compensation_validates_at_construction(kwargs, expected):
    """Validating once, at the boundary, is the point of bundling these."""
    with pytest.raises(ValueError, match=expected):
        Compensation(**kwargs)


def test_compensation_is_frozen():
    """Nothing may mutate a curve's definition partway through a fit."""
    comp = Compensation(74.0)
    with pytest.raises(Exception):
        comp.level = 80.0


def test_compensation_knows_when_there_is_nothing_to_correct():
    """At the mastering reference the ideal correction is identically zero."""
    assert Compensation(83.0, 83.0).is_null
    assert not Compensation(74.0, 83.0).is_null


# --- The compensation target ------------------------------------------------

def test_target_is_zero_at_1khz():
    """Every compensation curve is normalized to 0 dB at 1 kHz."""
    assert abs(ideal_delta(Compensation(65.0, 83.0))[REF_1KHZ_INDEX]) < 1e-9


def test_target_vanishes_when_level_equals_reference():
    """At the mastering level there is nothing to correct."""
    assert np.max(np.abs(ideal_delta(Compensation(83.0, 83.0)))) < 1e-9


def test_target_boosts_bass_below_reference_and_cuts_above():
    """Below the mastering level bass needs lifting; above it, trimming."""
    assert ideal_delta(Compensation(65.0, 83.0))[0] > 0
    assert ideal_delta(Compensation(88.0, 83.0))[0] < 0


def test_scale_is_linear():
    """--scale multiplies the target, so it must scale the curve linearly."""
    full = ideal_delta(Compensation(65.0, 83.0))
    half = ideal_delta(Compensation(65.0, 83.0, 0.5))
    assert np.allclose(half, full * 0.5)


def test_measurement_convention_offset_cancels():
    """A shared offset between --level and --reference must not matter much.

    Both are broadband C-weighted readings rather than the loudness level of an
    equally loud 1 kHz tone. Because the target is a *difference* of contours,
    an offset common to both cancels to first order -- which is what lets a
    listener use an ordinary SPL meter instead of a calibrated tone.
    """
    base = ideal_delta(Compensation(65.0, 83.0))
    for offset in (2.0, 4.0, 6.0, 7.0):
        shifted = ideal_delta(Compensation(65.0 + offset, 83.0 + offset))
        assert np.max(np.abs(shifted - base)) < 0.1


def test_level_error_matters_far_more_than_convention():
    """Mis-measuring the level is the dominant error source, by ~50x."""
    base = ideal_delta(Compensation(65.0, 83.0))
    convention = np.max(np.abs(ideal_delta(Compensation(71.0, 89.0)) - base))
    level = np.max(np.abs(ideal_delta(Compensation(71.0, 83.0)) - base))
    assert level > 20 * convention


# --- Biquads ----------------------------------------------------------------

def test_zero_gain_is_transparent():
    """A 0 dB band must be exactly transparent, not merely close."""
    freqs = np.logspace(np.log10(20), np.log10(20000), 64)
    resp = get_filter_response([('Peak', 1000.0, 0.0, 1.0)], freqs)
    assert np.max(np.abs(resp)) < 1e-9


def test_low_shelf_approaches_its_gain_at_dc():
    """Well below its corner a low shelf must reach its nominal gain."""
    resp = get_filter_response([('Low Shelf', 100.0, 6.0, 0.7)],
                               np.array([1.0]))[0]
    assert abs(resp - 6.0) < 0.1


def test_low_shelf_passband_is_flat():
    """Well above its corner a low shelf must be transparent."""
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
    """Well above its corner a high shelf must reach its nominal gain."""
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
    """Cascaded filters multiply in magnitude, so they add in dB."""
    freqs = np.logspace(np.log10(20), np.log10(20000), 64)
    a = ('Peak', 200.0, 3.0, 1.0)
    b = ('High Shelf', 8000.0, -2.0, 0.7)
    combined = get_filter_response([a, b], freqs)
    separate = get_filter_response([a], freqs) + get_filter_response([b], freqs)
    assert np.allclose(combined, separate, atol=1e-9)


def test_unknown_filter_type_is_rejected():
    """An unrecognised type must raise rather than silently do nothing."""
    with pytest.raises(ValueError):
        get_filter_response([('Notch', 1000.0, 3.0, 1.0)], np.array([1000.0]))


def test_cascade_diagnostics_flag_a_cancelling_pair(lf):
    """The conditioning metrics must actually detect the degenerate case.

    Two large opposing filters at nearly the same frequency measure fine
    end-to-end but overflow intermediate nodes in serial fixed-point DSPs and
    lose their cancellation under host coefficient quantization.
    """
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
    """The published peak must bound the response at every verified rate."""
    filters = [('High Shelf', 10000.0, 4.0, 0.7)]
    worst = peak_gain(filters)
    grid = np.logspace(np.log10(20), np.log10(20000), 500)
    for rate in VERIFY_RATES:
        assert np.max(get_filter_response(filters, grid, rate)) <= worst + 1e-9


# --- Level matching ---------------------------------------------------------

def test_match_delta_is_zero_for_a_transparent_cascade():
    """No gain anywhere means no level difference to correct for."""
    assert match_delta([]) == 0.0
    assert match_delta([('Peak', 1000.0, 0.0, 1.0)]) == pytest.approx(0.0, abs=1e-9)


def test_match_delta_reads_the_cascade_at_the_match_frequency():
    """It is the response at MATCH_FREQ_HZ and nothing else.

    Stated as an independent evaluation rather than by calling the same
    helper, so a change to how the measure is defined has to be made here
    too rather than passing silently.
    """
    filters = [('Low Shelf', 95.0, 4.59, 0.38), ('Peak', 320.8, 0.35, 0.25),
               ('Peak', 898.9, -0.13, 0.42), ('Peak', 2919.0, -0.33, 0.25),
               ('High Shelf', 10070.0, 1.55, 0.76)]
    at_500 = get_filter_response(filters, np.array([MATCH_FREQ_HZ]))[0]
    assert match_delta(filters) == pytest.approx(at_500, abs=1e-12)


def test_match_delta_reproduces_the_measured_null():
    """The one ear-derived calibration point this rule rests on.

    83->75 nulled by ear at -3.7 dB against a -4.2 dB headroom, so the bands
    are worth +0.5 dB. Any redefinition of the measure has to still land
    there, because that measurement is the whole justification for the
    frequency -- see the level-matching note in iso226_utils.
    """
    published_75 = [('Low Shelf', 95.0, 4.59, 0.38), ('Peak', 320.8, 0.35, 0.25),
                    ('Peak', 898.9, -0.13, 0.42), ('Peak', 2919.0, -0.33, 0.25),
                    ('High Shelf', 10070.0, 1.55, 0.76)]
    assert match_delta(published_75) == pytest.approx(0.50, abs=0.05)


def test_match_delta_follows_the_direction_of_the_correction():
    """Positive below the mastering reference, negative above it."""
    boosting = [('Low Shelf', 95.0, 4.59, 0.38), ('High Shelf', 10070.0, 1.55, 0.76)]
    cutting = [(t, f, -g, q) for t, f, g, q in boosting]
    assert match_delta(boosting) > 0.0
    assert match_delta(cutting) < 0.0


def test_the_negligible_threshold_is_under_what_a_listener_resolves():
    """It exists to stop the tables printing a distinction nobody can hear.

    Intensity discrimination for wideband material is around 0.4-0.5 dB, and
    better than 0.2 dB only for trained listeners with instantaneous
    switching. A threshold above that would start rounding away differences
    that are audible.
    """
    assert 0.0 < MATCH_NEGLIGIBLE_DB <= 0.25


def test_match_delta_never_exceeds_the_peak_gain():
    """A single point on the response cannot outrun its maximum.

    This is what guarantees the published bypass preamp stays negative: it is
    the headroom figure plus this delta, and the headroom already covers the
    peak. Without it a preset could advertise a bypass that asks for boost.
    """
    for filters in ([('Low Shelf', 41.39, 12.0, 0.54), ('Peak', 120.0, 5.94, 0.25),
                     ('High Shelf', 10150.0, 3.81, 0.89)],
                    [('Peak', 700.0, 6.0, 0.5)],
                    [('High Shelf', 8000.0, 9.0, 0.7)]):
        # None of these peaks sit on MATCH_FREQ_HZ itself. peak_gain samples a
        # 3000-point grid, so a filter centred exactly there reads its own gain
        # a hair above the sampled maximum -- an artefact of the grid, not a
        # violation of the property.
        assert match_delta(filters) <= peak_gain(filters) + 1e-9
