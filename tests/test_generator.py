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

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from check import parse_markdown_filters, parse_markdown_metadata  # noqa: E402
from iso226_utils import (  # noqa: E402
    EXTRAP_TOLERANCE_DB, ISO_FREQ, VERIFY_RATES, build_target,
    get_filter_response, ideal_delta,
)

# A hand-built result standing in for a generated one, so the format tests stay
# fast. Values are plausible but arbitrary.
SYNTHETIC = {
    'essential': [('Low Shelf', 77.5, 10.39, 0.42), ('Peak', 321.0, 2.39, 0.25),
                  ('Peak', 771.1, -1.78, 0.36), ('Peak', 5482.0, -0.62, 0.59),
                  ('High Shelf', 10921.3, 4.45, 0.68)],
    'refinement': [('Low Shelf', 41.3, -0.05, 0.55), ('Peak', 145.6, 0.01, 0.25),
                   ('Peak', 655.1, -0.01, 0.25), ('Peak', 1827.4, 0.01, 0.25),
                   ('High Shelf', 7125.0, 0.02, 2.00)],
    'error_essential': 0.0492,
    'error_all': 0.0520,
}
SYNTHETIC['all'] = SYNTHETIC['essential'] + SYNTHETIC['refinement']


# --- Format round-trips (fast) ----------------------------------------------

def test_markdown_round_trips_through_check(lf, tmp_path):
    """Every band written must come back with identical values, in order."""
    path = tmp_path / "filter_83_to_65_s1.0.md"
    lf.write_markdown_table(SYNTHETIC, 65.0, 83.0, 1.0, -9.5, str(path))

    recovered = parse_markdown_filters(str(path))
    assert len(recovered) == len(SYNTHETIC['all'])
    for original, parsed in zip(SYNTHETIC['all'], recovered):
        assert original[0] == parsed[0]                 # type string
        assert original[1] == pytest.approx(parsed[1])  # frequency
        assert original[2] == pytest.approx(parsed[2])  # gain
        assert original[3] == pytest.approx(parsed[3])  # Q


def test_first_five_parsed_bands_are_the_essential_set(lf, tmp_path):
    """check.py splits tiers positionally, so table order is load-bearing."""
    path = tmp_path / "filter_83_to_65_s1.0.md"
    lf.write_markdown_table(SYNTHETIC, 65.0, 83.0, 1.0, -9.5, str(path))
    recovered = parse_markdown_filters(str(path))
    assert recovered[:lf.TIER_SIZE] == [
        (f[0], f[1], f[2], f[3]) for f in SYNTHETIC['essential']]


@pytest.mark.parametrize("ref,scale", [(83.0, 1.0), (72.0, 1.0), (83.0, 0.65)])
def test_metadata_round_trips(lf, tmp_path, ref, scale):
    """check.py regenerates when these disagree, so they must survive writing."""
    path = tmp_path / "filter_83_to_65_s1.0.md"
    lf.write_markdown_table(SYNTHETIC, 65.0, ref, scale, -9.5, str(path))
    assert parse_markdown_metadata(str(path)) == (ref, scale)


def test_yaml_is_loadable_and_maps_every_band(lf, tmp_path):
    path = tmp_path / "filter_83_to_65_s1.0.yml"
    lf.write_camilladsp_yaml(SYNTHETIC, 65.0, 83.0, 1.0, -9.5, str(path))

    loaded = yaml.safe_load(path.read_text())
    bands = loaded['filters']
    assert len(bands) == len(SYNTHETIC['all'])

    expected_types = {'Low Shelf': 'Lowshelf', 'Peak': 'Peaking',
                      'High Shelf': 'Highshelf'}
    for i, (ftype, fc, gain, q_val) in enumerate(SYNTHETIC['all'], 1):
        params = bands[f'band_{i}']['parameters']
        assert bands[f'band_{i}']['type'] == 'Biquad'
        assert params['type'] == expected_types[ftype]
        assert params['freq'] == pytest.approx(fc)
        assert params['gain'] == pytest.approx(gain)
        assert params['q'] == pytest.approx(q_val)


def test_yaml_records_the_headroom(lf, tmp_path):
    """The headroom lives only in a comment, so it is easy to lose silently."""
    path = tmp_path / "filter_83_to_65_s1.0.yml"
    lf.write_camilladsp_yaml(SYNTHETIC, 65.0, 83.0, 1.0, -9.5, str(path))
    assert "-9.5 dB" in path.read_text()


# --- Headroom policy (fast) -------------------------------------------------

def test_headroom_is_rounded_away_from_zero(lf):
    """Rounding toward zero would leave the user clipping by up to 0.1 dB."""
    result = dict(SYNTHETIC)
    headroom = lf.headroom_adjustment(result)
    peak = max(lf.peak_gain(result['essential']), lf.peak_gain(result['all']))
    assert headroom <= -peak
    assert headroom == pytest.approx(round(headroom, 1))


def test_headroom_is_zero_when_nothing_is_boosted(lf):
    quiet = {'essential': [('Low Shelf', 60.0, -3.0, 0.7)],
             'all': [('Low Shelf', 60.0, -3.0, 0.7)]}
    assert lf.headroom_adjustment(quiet) == 0.0


def test_headroom_covers_the_essential_set_too(lf):
    """A listener entering only five bands uses the same published number."""
    result = dict(SYNTHETIC)
    headroom = lf.headroom_adjustment(result)
    for subset in (result['essential'], result['all']):
        for rate in VERIFY_RATES:
            grid = np.logspace(np.log10(20), np.log10(20000), 1500)
            assert np.max(get_filter_response(subset, grid, rate)) + headroom <= 1e-6


# --- Refusal suggestions (fast) ---------------------------------------------

def test_suggestions_actually_fit_the_budget(lf):
    """A suggestion the user cannot use is worse than no suggestion."""
    scale, level = lf.suggest_alternatives(50.0, 83.0, 1.0)
    budget = lf.MAX_HEADROOM
    assert scale is not None and scale < 1.0
    assert np.max(np.abs(ideal_delta(50.0, 83.0, scale))) <= budget
    assert level is not None and level > 50.0
    assert np.max(np.abs(ideal_delta(level, 83.0, 1.0))) <= budget


def test_no_suggestions_when_the_request_already_fits(lf):
    scale, level = lf.suggest_alternatives(75.0, 83.0, 1.0)
    assert scale is None
    assert level is None


def test_budget_check_passes_a_reachable_target(lf):
    lf.check_budget(SYNTHETIC, 65.0, 83.0, 1.0)  # must not raise


def test_budget_check_rejects_an_unreachable_target(lf):
    huge = {'essential': [('Low Shelf', 60.0, 12.0, 0.7)] * 3,
            'refinement': [], 'error_essential': 0.05, 'error_all': 0.05}
    huge['all'] = huge['essential']
    with pytest.raises(ValueError, match="--scale|--level"):
        lf.check_budget(huge, 50.0, 83.0, 1.0)


# --- Generated presets (slow) -----------------------------------------------

@pytest.mark.slow
def test_preset_is_nested(lf, preset):
    """Bands 1-5 of the full set must be exactly the essential set."""
    assert preset['all'][:lf.TIER_SIZE] == preset['essential']
    assert len(preset['all']) == 2 * lf.TIER_SIZE


@pytest.mark.slow
def test_preset_respects_the_host_gain_limit(lf, preset):
    """Roon's PEQ gain control stops at +/-12 dB; miniDSP at +/-16."""
    for ftype, fc, gain, q_val in preset['all']:
        assert abs(gain) <= lf.MAX_BAND_GAIN


@pytest.mark.slow
def test_preset_bands_stay_apart(lf, preset):
    """Adjacent bands must not converge into a cancelling pair."""
    for tier in (preset['essential'], preset['refinement']):
        freqs = [f[1] for f in tier]
        for lower, upper in zip(freqs, freqs[1:]):
            assert upper >= lf.MIN_SPACING_RATIO * lower * 0.999


@pytest.mark.slow
def test_preset_is_well_conditioned(lf, preset):
    """No intermediate stage may run hot enough to overflow a fixed-point host."""
    diag = lf.cascade_diagnostics(preset['all'])
    assert diag['stage_peak'] - diag['final_peak'] < 1.0
    assert diag['quantization_sensitivity'] < 0.15
    assert diag['opposing_neighbours'] < 2.0


@pytest.mark.slow
def test_preset_meets_its_advertised_error(lf, preset):
    """The published error must be measured from the published, rounded values."""
    grid, target, in_band = build_target(65.0, 83.0, 1.0)
    for filters, claimed in ((preset['essential'], preset['error_essential']),
                             (preset['all'], preset['error_all'])):
        actual = np.max(np.abs(
            (get_filter_response(filters, grid) - target)[in_band]))
        assert actual == pytest.approx(claimed, abs=1e-6)
        assert actual < 0.15


@pytest.mark.slow
def test_preset_extrapolation_stays_bounded(lf, preset):
    """Outside the ISO data the fit is constrained, not left to its own devices."""
    grid, target, in_band = build_target(65.0, 83.0, 1.0)
    error = get_filter_response(preset['all'], grid) - target
    outside = np.concatenate([error[:in_band.start], error[in_band.stop:]])
    assert np.max(np.abs(outside)) <= EXTRAP_TOLERANCE_DB + 1e-6


@pytest.mark.slow
def test_preset_has_no_band_above_12khz(lf, preset):
    """ISO 226 stops at 12.5 kHz and shelves near Nyquist are rate-sensitive."""
    assert max(f[1] for f in preset['all']) <= 12000.0


@pytest.mark.slow
def test_published_headroom_prevents_clipping_at_every_rate(lf, preset):
    """The safety property the whole headroom figure exists to guarantee."""
    headroom = lf.headroom_adjustment(preset)
    grid = np.logspace(np.log10(20), np.log10(20000), 3000)
    for filters in (preset['essential'], preset['all']):
        for rate in VERIFY_RATES:
            peak = np.max(get_filter_response(filters, grid, rate)) + headroom
            assert peak <= 0.0
