#!/usr/bin/env python3
"""Precompute the preset grid that the web API and the browser UI serve.

A single fit takes 20-45 s, which is far too slow to run inside an HTTP
request. It does not have to: the compensation curve depends on
``level - reference`` rather than on the two levels separately, so the whole
parameter space collapses to (offset, scale). This script fits that grid once
and writes it to JSON, after which the API is a dictionary lookup and needs
neither SciPy nor NumPy at runtime.

Two artifacts come out of one run, and they must stay in step -- they carry the
same ``generated_utc`` and ``tests/test_curves.py`` fails if they diverge:

* ``web/presets.json``  -- the filters themselves, served by ``web/app.py``.
* ``web/curves.json``   -- the ISO target and each band's response, sampled on
  the fit's own design grid, so ``ui/`` can plot both without reimplementing
  any of the maths in JavaScript.

Usage:
    python precompute_presets.py [--out web/presets.json]
                                 [--curves-out web/curves.json] [--jobs N]
"""

import argparse
import contextlib
import datetime
import importlib.util
import io
import json
import multiprocessing
import os
import sys

import numpy as np

from iso226_utils import (Compensation, DESIGN_FS, MAX_SCALE, MIN_SCALE,
                          MATCH_NEGLIGIBLE_DB, build_target,
                          get_filter_response, match_delta, peak_gain)

# The generator's module name is not importable directly (the file name has a
# hyphen, chosen for the CLI), so load it by path the way check.py does.
_SPEC = importlib.util.spec_from_file_location(
    "loudness_filters",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "loudness-filters.py"))
_GEN = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_GEN)

# Offsets span the committed ladder and a little either side. The floor is not
# enforced here: an over-budget combination is fitted, refused by
# check_budget, and recorded as refused so the API can explain itself.
MIN_OFFSET, MAX_OFFSET = -27, 7

# Nominal reference. Any pair with the same difference yields the same curve to
# within 0.125 dB across references 72-85 dB, which is the equivalence the
# README documents and the API reports back to the caller.
NOMINAL_REFERENCE = 83.0

# Curve samples are stored to 0.1 mdB. Five bands summed carry at worst
# 0.25 mdB of rounding against a 50 mdB accuracy target, which is invisible in
# a plot and two orders below the published residual.
CURVE_DECIMALS = 4


def preset_key(offset, scale):
    """The key both artifacts are indexed by. One function, so they agree."""
    return f"{offset:+d}|{scale:.2f}"


def all_scales():
    """The full scale ladder, for when partial compensation is served."""
    return [round(MIN_SCALE + 0.1 * i, 2)
            for i in range(int(round((MAX_SCALE - MIN_SCALE) / 0.1)) + 1)]


def grid(scales):
    """Every (offset, scale) pair the API can serve, in a stable order."""
    return [(offset, scale)
            for offset in range(MIN_OFFSET, MAX_OFFSET + 1)
            for scale in scales]


def _rounded(values):
    """A NumPy array as a JSON-ready list at the stored curve precision."""
    return np.round(values, CURVE_DECIMALS).tolist()


def _curve(comp, filters):
    """Plot data for one grid point, sampled on the fit's own design grid.

    The grid is the one the optimizer fitted against, not a prettier one chosen
    for the plot. That identity is what lets the UI's residual trace agree
    exactly with the published ``max_residual_db`` rather than approximately,
    and it means the flat-held extrapolation regions are visible for what they
    are instead of being cropped out of the picture.

    Bands are stored separately rather than pre-summed. Magnitudes multiply, so
    decibels add: the cascade response is the sum of these, and the UI gets
    per-band traces without evaluating a single biquad of its own.
    """
    fit = build_target(comp)
    curve = {"target": _rounded(fit.target)}
    if filters:
        curve["bands"] = [_rounded(get_filter_response([filt], fit.grid,
                                                       DESIGN_FS))
                          for filt in filters]
    return curve


def _fit(job):
    """Fit one grid point. Returns (key, entry, curve), refused or not."""
    offset, scale = job
    key = preset_key(offset, scale)
    comp = Compensation(level=NOMINAL_REFERENCE + offset,
                        reference=NOMINAL_REFERENCE, scale=scale)
    # calculate_filters reports progress on stderr; workers must stay quiet or
    # 350 interleaved multistart traces bury the grid's own output.
    with contextlib.redirect_stderr(io.StringIO()):
        try:
            result = _GEN.calculate_filters(comp)
            _GEN.check_budget(result, comp)
        except ValueError as exc:
            # A refused point still gets its target curve. "Here is the
            # correction you would need, and here is why it is not on offer"
            # is a better answer than an empty plot.
            return key, {"offset": offset, "scale": scale,
                         "refused": True, "reason": str(exc)}, _curve(comp, [])
        headroom = round(-peak_gain(result['filters']) - 0.049, 1)
        # Both figures are recomputed here rather than imported from the
        # generator's writers, which take a formatted page rather than a
        # dict; test_api_grid_matches_the_committed_presets is what holds
        # the two definitions together.
        _delta = match_delta(result['filters'])
        bypass = (headroom if abs(_delta) < MATCH_NEGLIGIBLE_DB
                  else round(headroom + _delta, 1))
    # At the mastering reference the correction is nothing, and the fit says so
    # by returning every band at 0.00 dB. Publish that as no filters at all,
    # the way PEQ/filter_83_to_83_s1.0.md does: five pass-through biquads are
    # something a user would otherwise be asked to type in for no effect.
    if all(gain == 0.0 for _, _, gain, _ in result['filters']):
        return key, {"offset": offset, "scale": scale, "refused": False,
                     "headroom_db": 0.0, "bypass_headroom_db": 0.0,
                     "max_residual_db": 0.0,
                     "target_met": True, "filters": []}, _curve(comp, [])
    return key, {
        "offset": offset,
        "scale": scale,
        "refused": False,
        "headroom_db": headroom,
        "bypass_headroom_db": bypass,
        "max_residual_db": round(result['error'], 4),
        "target_met": bool(result['target_met']),
        "filters": [{"band": i + 1, "type": ftype, "frequency": fc,
                     "gain": gain, "q": q}
                    for i, (ftype, fc, gain, q) in enumerate(result['filters'])],
    }, _curve(comp, result['filters'])


def _presets_payload(stamp, scales, presets):
    """The artifact web/app.py serves."""
    return {
        "generated_utc": stamp,
        "iso_edition": "ISO 226:2023",
        "band_count": _GEN.BAND_COUNT,
        "design_fs": DESIGN_FS,
        "nominal_reference_db": NOMINAL_REFERENCE,
        "offset_range_db": [MIN_OFFSET, MAX_OFFSET],
        "scales": sorted(scales),
        "scale_step": 0.1,
        "equivalence_tolerance_db": 0.125,
        "presets": dict(sorted(presets.items())),
    }


def _curves_payload(stamp, curves):
    """The artifact ui/ plots.

    ``grid_hz`` and ``in_band`` come from ``build_target`` rather than being
    restated, for the same reason ALPHA_R is derived from Table 1: there is one
    definition of where the ISO data ends, and this is not a second copy of it.
    """
    fit = build_target(Compensation(level=NOMINAL_REFERENCE))
    return {
        "generated_utc": stamp,
        "iso_edition": "ISO 226:2023",
        "design_fs": DESIGN_FS,
        "nominal_reference_db": NOMINAL_REFERENCE,
        "grid_hz": fit.grid.tolist(),
        "in_band": [fit.in_band.start, fit.in_band.stop],
        "curves": dict(sorted(curves.items())),
    }


def _write(path, payload, indent=None):
    """Write one artifact and report its size in KB.

    The curve file is written without indentation: it is 34,000 floats in
    182-element arrays, read only by a bundler, and pretty-printing it costs
    more than twice the bytes for a diff no one can read either way.
    """
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=indent, sort_keys=False,
                  separators=None if indent else (",", ":"))
        handle.write("\n")
    return os.path.getsize(path) / 1024


def main():
    """Fit the whole grid and write both artifacts."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="web/presets.json")
    parser.add_argument("--curves-out", default="web/curves.json")
    parser.add_argument("--jobs", type=int, default=multiprocessing.cpu_count())
    parser.add_argument(
        "--all-scales", action="store_true",
        help="fit the whole scale ladder (10x the work). The default fits "
             "full compensation only, which is what the API serves.")
    args = parser.parse_args()

    scales = all_scales() if args.all_scales else [MAX_SCALE]
    jobs = grid(scales)
    print(f"Fitting {len(jobs)} presets on {args.jobs} workers "
          f"(offsets {MIN_OFFSET:+d}..{MAX_OFFSET:+d}, "
          f"scales {', '.join(f'{s:g}' for s in scales)})", flush=True)

    presets, curves, done, refused = {}, {}, 0, 0
    with multiprocessing.Pool(args.jobs) as pool:
        for key, entry, curve in pool.imap_unordered(_fit, jobs):
            presets[key], curves[key] = entry, curve
            done += 1
            refused += entry["refused"]
            print(f"  [{done:3d}/{len(jobs)}] {key} "
                  f"{'refused' if entry['refused'] else 'ok'}", flush=True)

    # One timestamp for both files. It is what the tests compare to decide the
    # two artifacts came out of the same run.
    stamp = (datetime.datetime.now(datetime.timezone.utc)
             .replace(microsecond=0).isoformat())
    size = _write(args.out, _presets_payload(stamp, scales, presets), indent=1)
    print(f"\nWrote {args.out}: {len(presets)} presets "
          f"({refused} refused), {size:.0f} KB")
    size = _write(args.curves_out, _curves_payload(stamp, curves))
    print(f"Wrote {args.curves_out}: {len(curves)} curves, {size:.0f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
