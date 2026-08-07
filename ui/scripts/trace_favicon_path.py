#!/usr/bin/env python3
"""Derive the favicon's curve from the ISO 226 data, and check it still matches.

`ui/public/favicon.svg` is frozen artwork -- nothing regenerates it, and no test
holds it to the data. This script is the record of where its one path came from,
kept so the derivation can be reproduced and dated rather than asserted. Run it
to print the path, or with --check to compare against the committed file.

The mark is the compensation target itself: the 83 -> 65 dB curve, on a log
frequency axis spanning 20 Hz to 20 kHz, which is the window the plot and the
figures in `images/` both use. Every number below comes from `web/curves.json`,
which `precompute_presets.py` writes from the ISO 226:2023 contours. Nothing in
the shape was drawn by eye except the two adjustments named at the bottom, and
both are applied here rather than described, so the output is the committed
artwork and not an approximation of it.

    python3 ui/scripts/trace_favicon_path.py
    python3 ui/scripts/trace_favicon_path.py --check
"""

import argparse
import json
import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CURVES = REPO / 'web' / 'curves.json'
FAVICON = REPO / 'ui' / 'public' / 'favicon.svg'

#: The preset whose target is drawn: 18 dB below an 83 dB reference.
OFFSET_KEY = '-18|1.00'

#: The 64x64 viewBox, and the window mapped into it.
LOW_HZ, HIGH_HZ = 20.0, 20000.0
X_LEFT, X_SPAN = 10.0, 44.0
Y_BASE, Y_SPAN = 46.0, 36.0
DB_FLOOR, DB_RANGE = -1.5, 12.0

#: Anchors taken off the fitted grid, evenly spaced in log frequency.
ANCHOR_COUNT = 10

#: Hand adjustment 1 -- the smoothing overshoots a little below the trough,
#: putting two control points beneath the lowest point of the curve itself.
#: Pulled back to the trough. Visible at 64 px, invisible at 16 px, corrected
#: because the SVG is the source the other two icons are rasterized from.
OVERSHOOT = (
    'C 41.1 43.8 42.5 44.4 44.1 43.6',
    'C 41.1 43.7 42.5 43.9 44.1 43.6',
)

#: Hand adjustment 2 -- optical centring. The traced curve sits high in the
#: tile, leaving 9.6 units above it and 16.9 below. Shifting it down by 2.5
#: evens that out. It moves the whole path, so the shape is unchanged.
Y_NUDGE = 2.5


def _load_target() -> tuple[list[float], list[float]]:
    """The grid and the compensation target, as precompute_presets.py wrote them."""
    data = json.loads(CURVES.read_text(encoding='utf-8'))
    return data['grid_hz'], data['curves'][OFFSET_KEY]['target']


def _to_icon(hz: float, db: float) -> tuple[float, float]:
    """One (frequency, decibel) pair as a point in the 64x64 viewBox."""
    decades = math.log10(HIGH_HZ) - math.log10(LOW_HZ)
    x = X_LEFT + X_SPAN * (math.log10(hz) - math.log10(LOW_HZ)) / decades
    y = Y_BASE - Y_SPAN * (db - DB_FLOOR) / DB_RANGE
    return x, y


def _nearest(grid: list[float], wanted_log: float) -> int:
    """Index of the grid point closest to `wanted_log`, in log frequency.

    A function rather than a lambda inside the loop below: closing over the
    loop variable is safe only because `min` consumes it immediately, and that
    is not a property worth relying on.
    """
    return min(range(len(grid)), key=lambda k: abs(math.log10(grid[k]) - wanted_log))


def _anchors() -> list[tuple[float, float]]:
    """`ANCHOR_COUNT` points off the real grid, evenly spaced in log frequency."""
    grid, target = _load_target()
    low, high = math.log10(LOW_HZ), math.log10(HIGH_HZ)
    points = []
    for step in range(ANCHOR_COUNT):
        index = _nearest(grid, low + (high - low) * step / (ANCHOR_COUNT - 1))
        points.append(_to_icon(grid[index], target[index]))
    return points


def _catmull_rom(points: list[tuple[float, float]]) -> str:
    """A Catmull-Rom spline through `points`, as SVG cubic segments.

    Rounded to one decimal per number, which is the precision the committed
    path carries: at 64 units across, a tenth is a sixth of a pixel at 16 px.
    """
    out = [f'M {points[0][0]:.1f} {points[0][1]:.1f}']
    padded = [points[0]] + points + [points[-1]]
    for i in range(1, len(padded) - 2):
        before, start, end, after = padded[i - 1:i + 3]
        c1 = (start[0] + (end[0] - before[0]) / 6, start[1] + (end[1] - before[1]) / 6)
        c2 = (end[0] - (after[0] - start[0]) / 6, end[1] - (after[1] - start[1]) / 6)
        out.append(
            f'C {c1[0]:.1f} {c1[1]:.1f} {c2[0]:.1f} {c2[1]:.1f} '
            f'{end[0]:.1f} {end[1]:.1f}'
        )
    return ' '.join(out)


def _shift_down(path: str, amount: float) -> str:
    """Move every y in `path` by `amount`, leaving the command letters alone."""
    parts = path.split()
    shifted = []
    coordinate = 0
    for part in parts:
        if part in ('M', 'C'):
            shifted.append(part)
            continue
        value = float(part)
        shifted.append(f'{value + (amount if coordinate % 2 else 0.0):.1f}')
        coordinate += 1
    return ' '.join(shifted)


def build_path() -> str:
    """The committed path, from the data, including both hand adjustments."""
    traced = _catmull_rom(_anchors())
    before, after = OVERSHOOT
    if before not in traced:
        raise SystemExit(
            'The traced curve no longer contains the segment the overshoot fix '
            'was written against, so applying it blind would be wrong. The data '
            'or the mapping has changed; re-derive the icon deliberately.'
        )
    return _shift_down(traced.replace(before, after), Y_NUDGE)


def committed_path() -> str:
    """The `d` attribute of the one path in the committed favicon."""
    svg = FAVICON.read_text(encoding='utf-8')
    start = svg.index('d="') + 3
    return ' '.join(svg[start:svg.index('"', start)].split())


def main() -> int:
    """Print the derived path, or compare it with the committed artwork."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        '--check',
        action='store_true',
        help='compare against ui/public/favicon.svg and exit non-zero on a difference',
    )
    args = parser.parse_args()

    derived = build_path()
    if not args.check:
        print(derived)
        return 0

    published = committed_path()
    if derived == published:
        print(f'favicon.svg matches the {OFFSET_KEY} target it was traced from.')
        return 0
    print('The committed favicon no longer matches the derivation.')
    print(f'  derived:   {derived}')
    print(f'  committed: {published}')
    return 1


if __name__ == '__main__':
    sys.exit(main())
