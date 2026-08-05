#!/usr/bin/env python3
"""Precompute the preset grid that the web API serves.

A single fit takes 20-45 s, which is far too slow to run inside an HTTP
request. It does not have to: the compensation curve depends on
``level - reference`` rather than on the two levels separately, so the whole
parameter space collapses to (offset, scale). This script fits that grid once
and writes it to JSON, after which the API is a dictionary lookup and needs
neither SciPy nor NumPy at runtime.

Usage:
    python precompute_presets.py [--out web/presets.json] [--jobs N]
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

from iso226_utils import (Compensation, DESIGN_FS, MAX_SCALE, MIN_SCALE,
                          peak_gain)

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


def all_scales():
    """The full scale ladder, for when partial compensation is served."""
    return [round(MIN_SCALE + 0.1 * i, 2)
            for i in range(int(round((MAX_SCALE - MIN_SCALE) / 0.1)) + 1)]


def grid(scales):
    """Every (offset, scale) pair the API can serve, in a stable order."""
    return [(offset, scale)
            for offset in range(MIN_OFFSET, MAX_OFFSET + 1)
            for scale in scales]


def _fit(job):
    """Fit one grid point. Returns (key, entry) whether it succeeds or refuses."""
    offset, scale = job
    key = f"{offset:+d}|{scale:.2f}"
    comp = Compensation(level=NOMINAL_REFERENCE + offset,
                        reference=NOMINAL_REFERENCE, scale=scale)
    # calculate_filters reports progress on stderr; workers must stay quiet or
    # 350 interleaved multistart traces bury the grid's own output.
    with contextlib.redirect_stderr(io.StringIO()):
        try:
            result = _GEN.calculate_filters(comp)
            _GEN.check_budget(result, comp)
        except ValueError as exc:
            return key, {"offset": offset, "scale": scale,
                         "refused": True, "reason": str(exc)}
        headroom = round(-peak_gain(result['filters']) - 0.049, 1)
    # At the mastering reference the correction is nothing, and the fit says so
    # by returning every band at 0.00 dB. Publish that as no filters at all,
    # the way PEQ/filter_83_to_83_s1.0.md does: five pass-through biquads are
    # something a user would otherwise be asked to type in for no effect.
    if all(gain == 0.0 for _, _, gain, _ in result['filters']):
        return key, {"offset": offset, "scale": scale, "refused": False,
                     "headroom_db": 0.0, "max_residual_db": 0.0,
                     "target_met": True, "filters": []}
    return key, {
        "offset": offset,
        "scale": scale,
        "refused": False,
        "headroom_db": headroom,
        "max_residual_db": round(result['error'], 4),
        "target_met": bool(result['target_met']),
        "filters": [{"band": i + 1, "type": ftype, "frequency": fc,
                     "gain": gain, "q": q}
                    for i, (ftype, fc, gain, q) in enumerate(result['filters'])],
    }


def main():
    """Fit the whole grid and write it out."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="web/presets.json")
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

    presets, done, refused = {}, 0, 0
    with multiprocessing.Pool(args.jobs) as pool:
        for key, entry in pool.imap_unordered(_fit, jobs):
            presets[key] = entry
            done += 1
            refused += entry["refused"]
            print(f"  [{done:3d}/{len(jobs)}] {key} "
                  f"{'refused' if entry['refused'] else 'ok'}", flush=True)

    payload = {
        "generated_utc": datetime.datetime.now(datetime.timezone.utc)
                                 .replace(microsecond=0).isoformat(),
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
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=1, sort_keys=False)
        handle.write("\n")

    size = os.path.getsize(args.out) / 1024
    print(f"\nWrote {args.out}: {len(presets)} presets "
          f"({refused} refused), {size:.0f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
