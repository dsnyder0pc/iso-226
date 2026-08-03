"""
Tests for the generator and for the file formats that couple the two scripts.

`check.py` reads back what `loudness-filters.py` writes, matching filter type
strings and table columns by position. Nothing but a round-trip test notices
when one side of that contract changes, so the round-trip tests here are the
ones most likely to earn their keep during future edits.

The slow tests run the optimizer. Skip them with `-m "not slow"`.
"""

import os
import sys

import numpy as np
import pytest
import yaml

# The repo root must be on sys.path before the project modules import.
# pylint: disable=wrong-import-position
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from check import parse_markdown_filters, parse_markdown_metadata  # noqa: E402
from iso226_utils import (  # noqa: E402
    EXTRAP_TOLERANCE_DB, VERIFY_RATES, Compensation, build_target,
    get_filter_response, ideal_delta,
)

# A hand-built result standing in for a generated one, so the format tests stay
# fast. Values are plausible but arbitrary, and already at publication
# precision -- four significant figures of frequency, two decimals of gain and Q
# -- because that is what the writers are handed in practice.
SYNTHETIC = {
    'filters': [('Low Shelf', 77.5, 10.39, 0.42), ('Peak', 321.0, 2.39, 0.25),
                ('Peak', 771.1, -1.78, 0.36), ('Peak', 5482.0, -0.62, 0.59),
                ('High Shelf', 10920.0, 4.45, 0.68)],
    'error': 0.0492,
    'restarts': 7,
    'target_met': True,
}


# --- Format round-trips (fast) ----------------------------------------------

def test_markdown_round_trips_through_check(lf, tmp_path):
    """Every band written must come back with identical values, in order."""
    path = tmp_path / "filter_83_to_65_s1.0.md"
    lf.write_markdown_table(SYNTHETIC, Compensation(65.0), -9.5, str(path))

    recovered = parse_markdown_filters(str(path))
    assert len(recovered) == len(SYNTHETIC['filters'])
    for original, parsed in zip(SYNTHETIC['filters'], recovered):
        assert original[0] == parsed[0]                 # type string
        assert original[1] == pytest.approx(parsed[1])  # frequency
        assert original[2] == pytest.approx(parsed[2])  # gain
        assert original[3] == pytest.approx(parsed[3])  # Q


def test_markdown_publishes_every_band_in_order(lf, tmp_path):
    """check.py reads the table positionally, so row order is load-bearing."""
    path = tmp_path / "filter_83_to_65_s1.0.md"
    lf.write_markdown_table(SYNTHETIC, Compensation(65.0), -9.5, str(path))
    recovered = parse_markdown_filters(str(path))
    assert recovered == [(f[0], f[1], f[2], f[3]) for f in SYNTHETIC['filters']]


def test_frequency_survives_rendering_without_exponent_or_trailing_zero(lf,
                                                                       tmp_path):
    """A '%g' format would emit '1.2e+04' at 12 kHz, which parses back wrong.

    Four-significant-figure frequencies above 1 kHz are whole numbers, and a
    trailing '.0' implies a precision the fit does not have.
    """
    wide = dict(SYNTHETIC)
    wide['filters'] = [('Low Shelf', 38.67, 1.0, 0.5),
                       ('Peak', 262.6, 1.0, 0.5),
                       ('Peak', 900.0, 1.0, 0.5),
                       ('Peak', 2910.0, 1.0, 0.5),
                       ('High Shelf', 12000.0, 1.0, 0.5)]
    path = tmp_path / "filter_83_to_65_s1.0.md"
    lf.write_markdown_table(wide, Compensation(65.0), -9.5, str(path))
    text = path.read_text()
    assert "| 38.67 |" in text and "| 262.6 |" in text
    assert "| 900 |" in text and "| 2910 |" in text and "| 12000 |" in text
    assert "e+" not in text
    assert [f[1] for f in parse_markdown_filters(str(path))] == [
        38.67, 262.6, 900.0, 2910.0, 12000.0]


@pytest.mark.parametrize("ref,scale", [(83.0, 1.0), (72.0, 1.0), (83.0, 0.65)])
def test_metadata_round_trips(lf, tmp_path, ref, scale):
    """check.py regenerates when these disagree, so they must survive writing."""
    path = tmp_path / "filter_83_to_65_s1.0.md"
    lf.write_markdown_table(SYNTHETIC, Compensation(65.0, ref, scale), -9.5,
                            str(path))
    assert parse_markdown_metadata(str(path)) == (ref, scale)


def test_yaml_is_loadable_and_maps_every_band(lf, tmp_path):
    """Every band must survive as valid CamillaDSP YAML, with types mapped."""
    path = tmp_path / "filter_83_to_65_s1.0.yml"
    lf.write_camilladsp_yaml(SYNTHETIC, Compensation(65.0), -9.5, str(path))

    loaded = yaml.safe_load(path.read_text())
    bands = loaded['filters']
    assert len(bands) == len(SYNTHETIC['filters'])

    expected_types = {'Low Shelf': 'Lowshelf', 'Peak': 'Peaking',
                      'High Shelf': 'Highshelf'}
    for i, (ftype, fc, gain, q_val) in enumerate(SYNTHETIC['filters'], 1):
        params = bands[f'band_{i}']['parameters']
        assert bands[f'band_{i}']['type'] == 'Biquad'
        assert params['type'] == expected_types[ftype]
        assert params['freq'] == pytest.approx(fc)
        assert params['gain'] == pytest.approx(gain)
        assert params['q'] == pytest.approx(q_val)


def test_yaml_records_the_headroom(lf, tmp_path):
    """The headroom lives only in a comment, so it is easy to lose silently."""
    path = tmp_path / "filter_83_to_65_s1.0.yml"
    lf.write_camilladsp_yaml(SYNTHETIC, Compensation(65.0), -9.5, str(path))
    assert "-9.5 dB" in path.read_text()


# --- Headroom policy (fast) -------------------------------------------------

def test_headroom_is_rounded_away_from_zero(lf):
    """Rounding toward zero would leave the user clipping by up to 0.1 dB."""
    headroom = lf.headroom_adjustment(SYNTHETIC)
    assert headroom <= -lf.peak_gain(SYNTHETIC['filters'])
    assert headroom == pytest.approx(round(headroom, 1))


def test_headroom_is_zero_when_nothing_is_boosted(lf):
    """A set that only cuts needs no attenuation."""
    quiet = {'filters': [('Low Shelf', 60.0, -3.0, 0.7)]}
    assert lf.headroom_adjustment(quiet) == 0.0


def test_headroom_prevents_clipping_at_every_verified_rate(lf):
    """One published number has to hold at all of VERIFY_RATES, not just 44.1."""
    headroom = lf.headroom_adjustment(SYNTHETIC)
    grid = np.logspace(np.log10(20), np.log10(20000), 1500)
    for rate in VERIFY_RATES:
        peak = np.max(get_filter_response(SYNTHETIC['filters'], grid, rate))
        assert peak + headroom <= 1e-6


# --- Refusal suggestions (fast) ---------------------------------------------

def test_suggestions_actually_fit_the_budget(lf):
    """A suggestion the user cannot use is worse than no suggestion."""
    scale, level = lf.suggest_alternatives(Compensation(50.0))
    budget = lf.MAX_HEADROOM
    assert scale is not None and scale < 1.0
    assert np.max(np.abs(ideal_delta(Compensation(50.0, scale=scale)))) <= budget
    assert level is not None and level > 50.0
    assert np.max(np.abs(ideal_delta(Compensation(level)))) <= budget


def test_no_suggestions_when_the_request_already_fits(lf):
    """Do not tell someone to change parameters that are already fine."""
    scale, level = lf.suggest_alternatives(Compensation(75.0))
    assert scale is None
    assert level is None


def test_budget_check_passes_a_reachable_target(lf):
    """A target inside the gain budget must not raise."""
    lf.check_budget(SYNTHETIC, Compensation(65.0))  # must not raise


def test_budget_check_rejects_an_unreachable_target(lf):
    """Over budget must refuse, and must name a usable alternative."""
    huge = {'filters': [('Low Shelf', 60.0, 12.0, 0.7)] * 3, 'error': 0.05}
    with pytest.raises(ValueError, match="--scale|--level"):
        lf.check_budget(huge, Compensation(50.0))


# --- Publication precision (fast) -------------------------------------------

def test_publication_round_uses_significant_figures_for_frequency(lf):
    """Frequency sensitivity is fractional, so decimals are the wrong shape.

    0.1 Hz is marginal at 38 Hz and a hundred times finer than needed at 10 kHz;
    four significant figures holds margin at both ends.
    """
    rounded = lf.publication_round([
        ('Low Shelf', 38.6724, 7.8812, 0.2604),
        ('High Shelf', 9885.315, 1.4849, 0.8637),
    ])
    assert rounded[0] == ('Low Shelf', 38.67, 7.88, 0.26)
    assert rounded[1] == ('High Shelf', 9885.0, 1.48, 0.86)


def test_publication_round_is_idempotent(lf):
    """Rounding an already-published set must not move it again."""
    once = lf.publication_round([('Peak', 2909.574, -0.3162, 0.3591)])
    assert lf.publication_round(once) == once


# --- Search termination (slow) ----------------------------------------------

@pytest.mark.slow
def test_search_reports_what_it_spent(preset):
    """Restarts and target status are how a caller knows the search settled."""
    assert 1 <= preset['restarts'] <= 24
    assert isinstance(preset['target_met'], bool)
    assert preset['target_met'] == (preset['error'] <= 0.05)


@pytest.mark.slow
def test_search_returns_values_already_at_publication_precision(lf, preset):
    """The fit is scored on rounded values, so it must return rounded values.

    If the search returned an unrounded set, the error it advertises would be
    for numbers nobody receives.
    """
    assert lf.publication_round(preset['filters']) == preset['filters']


# --- Generated presets (slow) -----------------------------------------------

@pytest.mark.slow
def test_preset_has_the_expected_band_count(lf, preset):
    """The band count is part of the published file format."""
    assert len(preset['filters']) == lf.BAND_COUNT


@pytest.mark.slow
def test_preset_respects_the_host_gain_limit(lf, preset):
    """Roon's PEQ gain control stops at +/-12 dB; miniDSP at +/-16."""
    for _, _, gain, _ in preset['filters']:
        assert abs(gain) <= lf.MAX_BAND_GAIN


@pytest.mark.slow
def test_preset_bands_stay_apart(lf, preset):
    """Adjacent bands must not converge into a cancelling pair."""
    freqs = [f[1] for f in preset['filters']]
    for lower, upper in zip(freqs, freqs[1:]):
        assert upper >= lf.MIN_SPACING_RATIO * lower * 0.999


@pytest.mark.slow
def test_preset_respects_the_total_gain_budget(lf, preset):
    """The constraint that rules out large offsetting pairs must actually hold.

    Nothing downstream re-checks it, so if the search ever accepted an
    unconverged point this is what would catch it.
    """
    _, target, in_band = build_target(Compensation(65.0))
    budget = lf.GAIN_BUDGET_FACTOR * float(np.ptp(target[in_band]))
    assert sum(abs(f[2]) for f in preset['filters']) <= budget + 1e-6


@pytest.mark.slow
def test_preset_is_well_conditioned(lf, preset):
    """No intermediate stage may run hot enough to overflow a fixed-point host.

    The first two assertions measure the harms directly: an intermediate node
    running hotter than the final output, and the response moving under host
    coefficient quantization.

    ``opposing_neighbours`` is only a proxy for those, and its threshold used to
    be 2.0. That limit was never really exercised: the metric sorts bands by
    frequency and inspects adjacent pairs, and the old refinement tier
    interleaved near-zero-gain bands between the real ones, which broke the
    adjacencies. The 65 dB set read 0.100 across ten bands and 2.023 across the
    five that do the work -- so the number the test checked was an artifact of
    bands that changed nothing. With those gone the metric reports the real
    figure, and 3.0 leaves headroom over the worst case in the ladder while
    staying two orders of magnitude below an actual cancelling pair (the
    +17.33 dB / -16.12 dB example in the generator scores about 115).
    """
    diag = lf.cascade_diagnostics(preset['filters'])
    assert diag['stage_peak'] - diag['final_peak'] < 1.0
    assert diag['quantization_sensitivity'] < 0.15
    assert diag['opposing_neighbours'] < 3.0


@pytest.mark.slow
def test_preset_meets_its_advertised_error(preset):
    """The published error must be measured from the published, rounded values."""
    grid, target, in_band = build_target(Compensation(65.0))
    actual = np.max(np.abs(
        (get_filter_response(preset['filters'], grid) - target)[in_band]))
    assert actual == pytest.approx(preset['error'], abs=1e-6)
    assert actual < 0.15


@pytest.mark.slow
def test_preset_extrapolation_stays_bounded(preset):
    """Outside the ISO data the fit is constrained, not left to its own devices."""
    grid, target, in_band = build_target(Compensation(65.0))
    error = get_filter_response(preset['filters'], grid) - target
    outside = np.concatenate([error[:in_band.start], error[in_band.stop:]])
    assert np.max(np.abs(outside)) <= EXTRAP_TOLERANCE_DB + 1e-6


@pytest.mark.slow
def test_preset_has_no_band_above_12khz(preset):
    """ISO 226 stops at 12.5 kHz and shelves near Nyquist are rate-sensitive."""
    assert max(f[1] for f in preset['filters']) <= 12000.0


@pytest.mark.slow
def test_published_headroom_prevents_clipping_at_every_rate(lf, preset):
    """The safety property the whole headroom figure exists to guarantee."""
    headroom = lf.headroom_adjustment(preset)
    grid = np.logspace(np.log10(20), np.log10(20000), 3000)
    for rate in VERIFY_RATES:
        peak = np.max(get_filter_response(preset['filters'], grid, rate)) + headroom
        assert peak <= 0.0
