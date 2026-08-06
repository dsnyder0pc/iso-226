"""The plot data the browser UI draws.

``web/curves.json`` is the third generated artifact, after ``PEQ/``+``REW/``
and ``web/presets.json``. It exists so that ``ui/`` can draw the ISO target,
the achieved response and the residual between them without reimplementing any
of the maths in JavaScript -- the previous attempt at this UI drew a *made up*
target curve, which no test could have caught because nothing tied the picture
to the numbers.

These tests are that tie. Every array in the file is checked against the
function that should have produced it, and the residual implied by the curves
is checked against the residual the preset publishes.
"""

import json
import os

import numpy as np
import pytest

from iso226_utils import (Compensation, DESIGN_FS, build_target, design_grid,
                          get_filter_response)
from precompute_presets import CURVE_DECIMALS, NOMINAL_REFERENCE, preset_key

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Curves are stored rounded, so nothing can agree to better than half a unit
# in the last place kept.
STORAGE_TOLERANCE_DB = 0.5 * 10 ** -CURVE_DECIMALS + 1e-9


def _load(name):
    with open(os.path.join(ROOT, "web", name), encoding="utf-8") as handle:
        return json.load(handle)


@pytest.fixture(scope="module")
def presets():
    """The filters the API serves."""
    return _load("presets.json")


@pytest.fixture(scope="module")
def curves():
    """The plot data the UI draws."""
    return _load("curves.json")


# Requesting one fixture from another necessarily shadows its name.
# pylint: disable=redefined-outer-name
def _comp(entry):
    """The Compensation that produced one preset entry."""
    return Compensation(level=NOMINAL_REFERENCE + entry["offset"],
                        reference=NOMINAL_REFERENCE, scale=entry["scale"])


def _worst(a, b):
    """Largest absolute disagreement between two sampled curves."""
    return float(np.max(np.abs(np.asarray(a) - np.asarray(b))))


def test_the_curve_grid_is_the_grid_the_filters_were_fitted_on(curves):
    """Not a prettier grid chosen for the plot -- the optimizer's own.

    Everything else here depends on this: sampling anywhere else would make the
    residual computed from these curves merely close to the published one,
    instead of the same number.
    """
    assert curves["grid_hz"] == np.concatenate(design_grid()).tolist()
    fit = build_target(Compensation(level=NOMINAL_REFERENCE))
    assert curves["in_band"] == [fit.in_band.start, fit.in_band.stop]
    assert curves["design_fs"] == DESIGN_FS


def test_both_artifacts_came_out_of_the_same_run(presets, curves):
    """presets.json and curves.json are written together and must stay together.

    Regenerating one without the other would leave the UI plotting a response
    that belongs to different filters from the ones it lists in its table --
    exactly the failure test_api_grid_matches_the_committed_presets guards
    against between the API and PEQ/.
    """
    assert curves["generated_utc"] == presets["generated_utc"], (
        "web/curves.json and web/presets.json are from different runs. "
        "Rerun precompute_presets.py, which writes both.")
    assert set(curves["curves"]) == set(presets["presets"])


def test_every_target_curve_is_the_iso_target(presets, curves):
    """The target is ideal_delta on the design grid, flat-held at the edges.

    This is the assertion the fabricated version could never have passed.
    """
    for key, entry in presets["presets"].items():
        expected = build_target(_comp(entry)).target
        assert _worst(curves["curves"][key]["target"],
                      expected) <= STORAGE_TOLERANCE_DB, (
            f"{key}: stored target is not ideal_delta on the design grid")


def test_every_band_curve_is_the_filter_the_preset_publishes(presets, curves):
    """Each stored band is that one published filter's magnitude response."""
    checked = 0
    for key, entry in presets["presets"].items():
        if entry["refused"] or not entry["filters"]:
            continue
        grid = np.array(curves["grid_hz"])
        bands = curves["curves"][key]["bands"]
        assert len(bands) == len(entry["filters"])
        for band, filt in zip(bands, entry["filters"]):
            expected = get_filter_response(
                [(filt["type"], filt["frequency"], filt["gain"], filt["q"])],
                grid, DESIGN_FS)
            assert _worst(band, expected) <= STORAGE_TOLERANCE_DB, (
                f"{key} band {filt['band']}: stored curve is not the response "
                f"of the filter the preset publishes")
            checked += 1
    assert checked >= 100, "expected the whole grid's bands to be compared"


def test_the_residual_the_curves_imply_is_the_published_residual(presets,
                                                                 curves):
    """Summing the band curves and subtracting the target reproduces the error.

    Magnitudes multiply, so decibels add: the sum of the per-band curves is the
    cascade response exactly, and its worst in-band deviation from the target
    is what the preset quotes as max_residual_db. The UI can therefore draw a
    residual trace that cannot contradict the number printed beside it.
    """
    low, high = curves["in_band"]
    for key, entry in presets["presets"].items():
        if entry["refused"] or not entry["filters"]:
            continue
        curve = curves["curves"][key]
        response = np.sum(np.array(curve["bands"]), axis=0)
        residual = response - np.array(curve["target"])
        worst = float(np.max(np.abs(residual[low:high])))
        # Five rounded band curves and a rounded target, so the sum carries
        # six roundings; anything beyond that is a real disagreement.
        assert abs(worst - entry["max_residual_db"]) <= 12 * \
            STORAGE_TOLERANCE_DB, (
            f"{key}: curves imply {worst:.4f} dB residual but the preset "
            f"publishes {entry['max_residual_db']:.4f} dB")


def test_refused_and_null_presets_keep_a_target_but_have_no_bands(presets,
                                                                 curves):
    """A refusal still gets a picture: the correction it declines to make.

    The pass-through preset at the mastering reference is the same shape --
    a target of zeros and nothing to plot against it.
    """
    seen = {"refused": 0, "null": 0}
    for key, entry in presets["presets"].items():
        if not entry["refused"] and entry["filters"]:
            continue
        curve = curves["curves"][key]
        assert "bands" not in curve, f"{key} has no filters but stores bands"
        assert len(curve["target"]) == len(curves["grid_hz"])
        seen["refused" if entry["refused"] else "null"] += 1
    assert seen["refused"] >= 1 and seen["null"] == 1, (
        f"expected refusals and exactly one pass-through preset, got {seen}")


def test_the_null_preset_asks_for_no_correction(presets, curves):
    """At the mastering reference the target is zero everywhere."""
    key = preset_key(0, 1.0)
    assert presets["presets"][key]["filters"] == []
    assert not np.any(np.array(curves["curves"][key]["target"]))


def test_the_ui_keeps_no_copy_of_the_generated_data(curves):
    """ui/ reads web/ directly; a copy would be free to drift and silently did.

    The AI Studio prototype this replaced carried a byte-identical duplicate of
    presets.json in its own source tree, which nothing would have noticed going
    stale.
    """
    assert curves  # the artifact this rule exists to protect
    strays = []
    for where, dirs, files in os.walk(os.path.join(ROOT, "ui")):
        dirs[:] = [d for d in dirs if d not in ("node_modules", "dist")]
        strays += [os.path.join(where, name) for name in files
                   if name in ("presets.json", "curves.json")]
    assert not strays, (
        f"ui/ must import web/*.json, not copy it: {strays}")
