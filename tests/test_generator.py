"""
Tests for the generator and for the file formats that couple the two scripts.

`check.py` reads back what `loudness-filters.py` writes, matching filter type
strings and table columns by position. Nothing but a round-trip test notices
when one side of that contract changes, so the round-trip tests here are the
ones most likely to earn their keep during future edits.

The slow tests run the optimizer. Skip them with `-m "not slow"`.
"""

import json
import os
import re
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
    MATCH_NEGLIGIBLE_DB, get_filter_response, ideal_delta, match_delta,
    peak_gain,
)

# The published bypass figure, read back out of a generated page. The sentence
# carrying it is deliberately not a recipe -- every host applies a flat
# attenuation somewhere different -- so this matches the figure and its noun,
# not an instruction.
BYPASS_RE = r"unfiltered signal at\s*(-?[0-9.]+)\s*dB"

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


def test_embedded_plot_does_not_disturb_the_table(lf, tmp_path):
    """The image line sits in the same file check.py parses.

    It is not a table row and must not be read as one -- nor may the caption
    around it, which mentions the values the parser is looking for.
    """
    path = tmp_path / "filter_83_to_65_s1.0.md"
    lf.write_markdown_table(SYNTHETIC, Compensation(65.0), -9.5, str(path),
                            "../images/filter_83_to_65_s1.0.png")
    text = path.read_text()
    assert "![" in text and "../images/filter_83_to_65_s1.0.png" in text
    assert parse_markdown_filters(str(path)) == [
        (f[0], f[1], f[2], f[3]) for f in SYNTHETIC['filters']]
    assert parse_markdown_metadata(str(path)) == (83.0, 1.0)


def test_a_rule_separates_the_table_from_the_plot(lf, tmp_path):
    """Markdown collapses blank lines, so the gap has to be a real block.

    Losing this is invisible in the source and only shows up as a plot jammed
    against the table's bottom border on the rendered page. The blank line
    before the rule is load-bearing too: without it the preceding line becomes
    a setext heading instead.
    """
    path = tmp_path / "filter_83_to_65_s1.0.md"
    lf.write_markdown_table(SYNTHETIC, Compensation(65.0), -9.5, str(path),
                            "filter_83_to_65_s1.0.png")
    lines = path.read_text().splitlines()
    image = next(i for i, line in enumerate(lines) if line.startswith("!["))
    rule = lines.index("---", image - 3, image)
    assert lines[rule - 1] == "", "the rule would be read as a setext heading"
    assert lines[rule + 1] == ""


def test_no_plot_is_embedded_unless_one_is_named(lf, tmp_path):
    """A page written without an image must not link one that is not there."""
    path = tmp_path / "filter_83_to_65_s1.0.md"
    lf.write_markdown_table(SYNTHETIC, Compensation(65.0), -9.5, str(path))
    assert "![" not in path.read_text()


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


# --- Level-matched bypass (fast) --------------------------------------------

def test_bypass_headroom_is_the_headroom_plus_the_match_delta(lf):
    """The published figure is those two numbers and nothing else."""
    headroom = lf.headroom_adjustment(SYNTHETIC)
    expected = headroom + match_delta(SYNTHETIC['filters'])
    assert lf.bypass_headroom(SYNTHETIC, headroom) == pytest.approx(expected, abs=0.05)


def test_bypass_headroom_never_asks_for_boost(lf):
    """A bypass preamp above 0 dB would be an instruction to clip.

    It cannot happen -- the loudness a cascade adds is bounded by its peak,
    which the headroom already covers -- but the arithmetic combines two
    separately rounded numbers, so it is worth pinning.
    """
    for filters in (SYNTHETIC['filters'],
                    [('Low Shelf', 41.39, 12.0, 0.54), ('Peak', 120.0, 5.94, 0.25)],
                    [('High Shelf', 10150.0, 3.81, 0.89)]):
        result = {'filters': filters}
        assert lf.bypass_headroom(result, lf.headroom_adjustment(result)) <= 0.0


def test_bypass_snaps_to_the_headroom_when_the_difference_is_inaudible(lf):
    """Two numbers a tenth apart invite a distinction nobody can hear.

    Near the mastering reference the correction barely moves the level, so
    the bypass collapses onto the headroom rather than publishing -1.4 dB
    beside -1.6 dB. Away from it the two must stay apart.
    """
    tiny = {'filters': [('Low Shelf', 60.0, 0.4, 0.4)]}
    headroom = lf.headroom_adjustment(tiny)
    assert abs(match_delta(tiny['filters'])) < MATCH_NEGLIGIBLE_DB
    assert lf.bypass_headroom(tiny, headroom) == headroom

    real = {'filters': [('Low Shelf', 95.0, 4.59, 0.38)]}
    headroom = lf.headroom_adjustment(real)
    assert lf.bypass_headroom(real, headroom) != headroom


def test_markdown_publishes_the_bypass_beside_the_headroom(lf, tmp_path):
    """Both numbers must reach the page, and the reader must be told which."""
    path = tmp_path / "filter_83_to_65_s1.0.md"
    lf.write_markdown_table(SYNTHETIC, Compensation(65.0), -9.5, str(path))
    text = path.read_text(encoding="utf-8")
    bypass = lf.bypass_headroom(SYNTHETIC, -9.5)
    assert "Headroom adjustment: -9.5 dB" in text
    assert f"unfiltered signal at {bypass:.1f} dB" in text


def test_the_bypass_line_is_not_mistaken_for_a_table_row(lf, tmp_path):
    """It is prose full of dB figures sitting above the table check.py parses.

    The parser takes any pipe-delimited line with enough columns, and the
    headroom regex takes the first match in the file, so a new line carrying
    numbers is exactly the shape of thing that breaks one of them.
    """
    path = tmp_path / "filter_83_to_65_s1.0.md"
    lf.write_markdown_table(SYNTHETIC, Compensation(65.0), -9.5, str(path))

    recovered = parse_markdown_filters(str(path))
    assert len(recovered) == len(SYNTHETIC['filters'])
    for original, parsed in zip(SYNTHETIC['filters'], recovered):
        assert original[0] == parsed[0]
        assert original[1:] == pytest.approx(parsed[1:])
    text = path.read_text(encoding="utf-8")
    match = re.search(r"Headroom adjustment:\s*(-?[0-9.]+)\s*dB", text)
    assert match and float(match.group(1)) == -9.5


def test_the_null_preset_offers_no_bypass(lf, tmp_path):
    """With nothing to switch off there is nothing to compare against."""
    path = tmp_path / "filter_83_to_83_s1.0.md"
    null = {'filters': [('Peak', 1000.0, 0.0, 1.0)], 'error': 0.0,
            'restarts': 1, 'target_met': True}
    lf.write_markdown_table(null, Compensation(83.0), 0.0, str(path))
    assert "bypass" not in path.read_text(encoding="utf-8").lower()


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


# --- The shipped ladder -----------------------------------------------------
# Everything above tests the generator. These test what is actually committed
# in PEQ/ and REW/, which is what users download and what the README makes
# claims about. They are fast: parsing and a frequency response, no fitting.
# Nothing else notices when a shipped preset drifts out of budget, or when the
# README and the files disagree about where the floor is.

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _committed_presets():
    """Every preset markdown file in PEQ/, as (stem, path) pairs."""
    peq = os.path.join(ROOT, "PEQ")
    return sorted((os.path.splitext(name)[0], os.path.join(peq, name))
                  for name in os.listdir(peq) if name.endswith(".md"))


@pytest.mark.parametrize("stem,path", _committed_presets())
def test_committed_preset_fits_the_headroom_budget(lf, stem, path):
    """No shipped preset may need more headroom than a host PEQ can give.

    The floor is emergent -- check_budget refuses whatever does not fit -- so
    the only thing standing between a bad ladder entry and a user is this.

    The reference rung carries no filters at all (listening at the mastering
    level needs no correction), which is a valid preset and not an empty one.
    """
    filters = parse_markdown_filters(path)
    if not filters:
        with open(path, encoding="utf-8") as handle:
            assert "No Compensation Needed" in handle.read(), (
                f"{stem} has no filter table and does not say why")
        return
    assert peak_gain(filters) <= lf.MAX_HEADROOM + 1e-9, (
        f"{stem} needs more than {lf.MAX_HEADROOM:g} dB of headroom")


@pytest.mark.parametrize("stem,path", _committed_presets())
def test_committed_preset_publishes_its_own_headroom(stem, path):
    """The printed headroom must match the filters printed beside it.

    Published away from zero to 0.1 dB, so it may exceed the computed peak by
    up to that rounding but must never fall short of it -- a short figure
    clips.
    """
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    if not parse_markdown_filters(path):
        assert "no headroom adjustment" in text.lower(), (
            f"{stem} has no filters but does not say headroom is unnecessary")
        return
    match = re.search(r"Headroom adjustment:\s*(-?[0-9.]+)\s*dB", text)
    assert match, f"{stem} does not publish a headroom figure"
    published = float(match.group(1))
    computed = peak_gain(parse_markdown_filters(path))
    assert -published >= computed - 1e-9, (
        f"{stem} publishes {published} dB but needs {-computed:.4f} dB")
    assert -published - computed <= 0.1 + 1e-9, (
        f"{stem} publishes {published} dB, more than 0.1 dB of slack")


@pytest.mark.parametrize("stem,path", _committed_presets())
def test_committed_preset_publishes_its_own_bypass(lf, stem, path):
    """The bypass preamp must match the bands printed beside it.

    Recomputed from the file's own filter rows, so a table regenerated by an
    older build -- or edited by hand -- fails here rather than sending someone
    into a listening comparison with a level difference still in it.
    """
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    filters = parse_markdown_filters(path)
    if not filters:
        assert not re.search(BYPASS_RE, text), (
            f"{stem} has no filters but still offers a bypass")
        return
    match = re.search(BYPASS_RE, text)
    assert match, f"{stem} does not publish a level-matched bypass"
    result = {'filters': filters}
    expected = lf.bypass_headroom(result, lf.headroom_adjustment(result))
    assert float(match.group(1)) == pytest.approx(expected, abs=1e-9), (
        f"{stem} publishes a bypass of {match.group(1)} dB, "
        f"but its own bands give {expected:.1f} dB")


@pytest.mark.parametrize("stem,path", _committed_presets())
def test_committed_preset_embeds_a_plot_that_exists(stem, path):
    """The page and its figure are written by one command into two directories.

    A rendered table with a broken image is worse than one with no image: it
    tells a listener entering filters by hand that something is missing without
    saying what. The link is relative and crosses out of PEQ/, so resolve it
    the way a renderer would rather than assuming the layout.
    """
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    match = re.search(r"!\[[^\]]*\]\(([^)]+)\)", text)
    assert match, f"{stem} embeds no response plot"
    target = os.path.normpath(os.path.join(os.path.dirname(path), match.group(1)))
    assert os.path.exists(target), (
        f"{stem} links {match.group(1)}, which does not exist. "
        f"Rerun regenerate.py.")
    assert os.path.basename(target) == f"{stem}.png", (
        f"{stem} embeds {os.path.basename(target)} -- another preset's plot")


def test_every_committed_table_has_its_yaml():
    """The two directories hold the same ladder in two formats."""
    tables = {stem for stem, _ in _committed_presets()}
    configs = {os.path.splitext(name)[0]
               for name in os.listdir(os.path.join(ROOT, "REW"))
               if name.endswith(".yml")}
    assert tables == configs, (
        f"PEQ/ and REW/ ship different presets: {tables ^ configs}")


def test_api_grid_matches_the_committed_presets():
    """web/presets.json and the committed tables must publish the same filters.

    They are produced by different commands -- regenerate.py and
    precompute_presets.py -- so a maths change that reruns one and not the
    other would leave the website serving filters the repository does not
    publish. Nothing else notices.
    """
    with open(os.path.join(ROOT, "web", "presets.json"), encoding="utf-8") as fh:
        grid = json.load(fh)["presets"]

    checked = 0
    for stem, path in _committed_presets():
        level = int(stem.split("_to_")[1].split("_")[0])
        entry = grid.get(f"{level - 83:+d}|1.00")
        assert entry is not None and not entry["refused"], (
            f"{stem} ships in PEQ/ but the API grid cannot serve it")
        published = [tuple(row) for row in parse_markdown_filters(path)]
        served = [(f["type"], f["frequency"], f["gain"], f["q"])
                  for f in entry["filters"]]
        assert published == served, (
            f"{stem}: PEQ/ and web/presets.json disagree. "
            f"Rerun both regenerate.py and precompute_presets.py.")
        # The bypass preamp is computed independently on each side, from the
        # same filters, so it catches a level-matching change that reached one
        # writer and not the other -- which the filter rows above cannot.
        with open(path, encoding="utf-8") as fh:
            match = re.search(BYPASS_RE, fh.read())
        expected = float(match.group(1)) if match else 0.0
        assert entry["bypass_headroom_db"] == pytest.approx(expected, abs=1e-9), (
            f"{stem}: PEQ/ publishes a bypass of {expected} dB and the API "
            f"grid {entry['bypass_headroom_db']} dB. "
            f"Rerun both regenerate.py and precompute_presets.py.")
        checked += 1
    assert checked >= 10, "expected the whole committed ladder to be compared"
