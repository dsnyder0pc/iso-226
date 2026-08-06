/**
 * Where every trace lands on the page.
 *
 * Both vertical scales are fixed once, from the whole ladder, rather than
 * fitted to the level on screen. Dragging the slider then *shows* the
 * correction growing and the residual worsening at the quiet end, instead of
 * rescaling under the cursor and making every level look alike.
 */
import { levelData, meta } from '../data';
import type { LevelData } from '../data/types';

/**
 * The vertical offset the response panel is drawn at: the headroom.
 *
 * The committed plots in `PEQ/` add it to both traces and mark 0 dB as the
 * clipping limit, and this has to match them. Without it a compensation curve
 * sits almost entirely above zero and reads as a proposal to boost and clip,
 * when what it actually asks for is attenuation everywhere except the extremes.
 *
 * The residual panel is deliberately *not* shifted. Headroom is a constant, so
 * it cancels out of `response - target` — the error is a property of the
 * cascade, not of the preamp in front of it.
 */
export function displayShift(data: LevelData): number {
  if (data.kind === 'served') {
    return data.headroomDb;
  }
  if (data.kind === 'refused') {
    // No filter set exists here, so there is no published headroom. Draw it
    // against the headroom it would need, which is the reason it is refused.
    return -Math.max(...data.target);
  }
  return 0;
}

export const WIDTH = 1000;
export const MARGIN = { left: 58, right: 18, top: 14, bottom: 26 };
export const MAIN_HEIGHT = 300;
export const GAP = 38;
export const RESIDUAL_HEIGHT = 92;
export const HEIGHT =
  MARGIN.top + MAIN_HEIGHT + GAP + RESIDUAL_HEIGHT + MARGIN.bottom;

const PLOT_WIDTH = WIDTH - MARGIN.left - MARGIN.right;
const MAIN_TOP = MARGIN.top;
const RESIDUAL_TOP = MARGIN.top + MAIN_HEIGHT + GAP;

/**
 * The window is 20 Hz-20 kHz, matching the figures in `images/` that the PEQ
 * tables embed — a listener comparing the page against a preset's own plot
 * should be looking at the same picture.
 *
 * The data still runs from 10 Hz, because the optimizer's grid does and the
 * residual has to be measured over the slice the objective used. This crops
 * the *view*, and it crops it exactly at `in_band`, whose first index is
 * 20 Hz to within 4e-15 — so the sub-20 Hz extrapolation block comes off
 * whole and nothing in-band is touched.
 *
 * What this deliberately stops showing: the cascade's true peak lies between
 * 10 and 20 Hz, where a low shelf is still climbing to its plateau, and
 * `peak_gain` in iso226_utils.py does not look there either. Up to 0.75 dB of
 * the response therefore sits above 0 dBFS off the left edge of this view.
 * The published figures have always cropped it the same way.
 */
const VISIBLE_FROM = meta.inBand[0];

const first = meta.gridHz[VISIBLE_FROM] ?? 20;
const last = meta.gridHz[meta.gridHz.length - 1] ?? 20000;
const LOG_MIN = Math.log10(first);
const LOG_MAX = Math.log10(last);

/** Horizontal position of a frequency, in viewBox units. */
export function xOf(hz: number): number {
  const t = (Math.log10(hz) - LOG_MIN) / (LOG_MAX - LOG_MIN);
  return MARGIN.left + t * PLOT_WIDTH;
}

function extremes(): { gain: [number, number]; residual: number } {
  let low = 0;
  let high = 0;
  let residual = 0;
  for (const offset of allOffsets()) {
    const data = levelData(offset);
    if (data.kind === 'unknown') {
      continue;
    }
    const shift = displayShift(data);
    // Only what is on screen sets the scale.
    for (const db of data.target.slice(VISIBLE_FROM)) {
      low = Math.min(low, db + shift);
      high = Math.max(high, db + shift);
    }
    if (data.kind === 'served') {
      for (const db of data.response.slice(VISIBLE_FROM)) {
        low = Math.min(low, db + shift);
        high = Math.max(high, db + shift);
      }
    }
    if (data.kind === 'served') {
      // In-band only. Outside the ISO range the fit is merely *constrained*,
      // to a 1.5 dB tolerance rather than the 0.05 dB accuracy target, so
      // including the held regions here would scale the strip to the loosest
      // number on the page and flatten the residual it exists to show.
      for (const db of data.residual.slice(meta.inBand[0], meta.inBand[1])) {
        residual = Math.max(residual, Math.abs(db));
      }
    }
  }
  return { gain: [low, high], residual };
}

function allOffsets(): number[] {
  const offsets: number[] = [];
  for (let offset = meta.fitted.min; offset <= meta.fitted.max; offset += 1) {
    offsets.push(offset);
  }
  return offsets;
}

function roundedTo(value: number, step: number): number {
  return Math.ceil(value / step) * step;
}

const span = extremes();

/** Fixed dB window for the response panel, padded out to whole decibels. */
export const GAIN_RANGE: [number, number] = [
  Math.floor(span.gain[0]) - 1,
  Math.ceil(span.gain[1]) + 1,
];

/** Fixed symmetric window for the residual strip. */
export const RESIDUAL_BOUND = Math.max(0.05, roundedTo(span.residual * 1.15, 0.05));

export function yOfGain(db: number): number {
  const [low, high] = GAIN_RANGE;
  return MAIN_TOP + ((high - db) / (high - low)) * MAIN_HEIGHT;
}

export function yOfResidual(db: number): number {
  const t = (RESIDUAL_BOUND - db) / (2 * RESIDUAL_BOUND);
  return RESIDUAL_TOP + t * RESIDUAL_HEIGHT;
}

export const panels = {
  main: { top: MAIN_TOP, height: MAIN_HEIGHT, bottom: MAIN_TOP + MAIN_HEIGHT },
  residual: {
    top: RESIDUAL_TOP,
    height: RESIDUAL_HEIGHT,
    bottom: RESIDUAL_TOP + RESIDUAL_HEIGHT,
  },
  left: MARGIN.left,
  right: MARGIN.left + PLOT_WIDTH,
};

/** ISO 266 preferred frequencies, labelled where there is room for a label. */
export const FREQUENCY_TICKS: { hz: number; label: string | null }[] = [
  { hz: 20, label: '20' },
  { hz: 50, label: '50' },
  { hz: 100, label: '100' },
  { hz: 200, label: '200' },
  { hz: 500, label: '500' },
  { hz: 1000, label: '1k' },
  { hz: 2000, label: '2k' },
  { hz: 5000, label: '5k' },
  { hz: 10000, label: '10k' },
  { hz: 20000, label: '20k' },
];

export function gainTicks(): number[] {
  const [low, high] = GAIN_RANGE;
  // The committed grid spans -5..+16 dB, which wants 2 dB gridlines; the wider
  // steps are here so a future grid does not end up with forty of them.
  const step = [2, 5, 10].find((candidate) => (high - low) / candidate <= 12) ?? 20;
  const ticks: number[] = [];
  for (let db = Math.ceil(low / step) * step; db <= high; db += step) {
    ticks.push(db);
  }
  return ticks;
}

export function residualTicks(): number[] {
  return [RESIDUAL_BOUND, 0, -RESIDUAL_BOUND];
}

/**
 * An SVG path through one sampled curve.
 *
 * The grid is the optimizer's, so the points are where the fit was actually
 * evaluated: a straight segment between them draws exactly what was measured
 * and nothing that was not. No smoothing, for that reason.
 */
export function pathOf(values: number[], yOf: (db: number) => number): string {
  let d = '';
  values.slice(VISIBLE_FROM).forEach((db, offset) => {
    const hz = meta.gridHz[VISIBLE_FROM + offset];
    if (hz === undefined) {
      return;
    }
    d += `${offset === 0 ? 'M' : 'L'}${xOf(hz).toFixed(2)} ${yOf(db).toFixed(2)}`;
  });
  return d;
}

interface Paths {
  target: string;
  response: string | null;
  residual: string | null;
  bands: string[];
  /** Where the flat reference sits: the preamp these curves are drawn against. */
  shift: number;
}

const pathCache = new Map<number, Paths>();

function shifted(values: number[], by: number): number[] {
  return values.map((db) => db + by);
}

/** Path strings for one level, built once and reused for the rest of the session. */
export function pathsFor(offset: number): Paths | null {
  const hit = pathCache.get(offset);
  if (hit) {
    return hit;
  }
  const data = levelData(offset);
  if (data.kind === 'unknown') {
    return null;
  }
  const shift = displayShift(data);
  const built: Paths =
    data.kind === 'served'
      ? {
          target: pathOf(shifted(data.target, shift), yOfGain),
          response: pathOf(shifted(data.response, shift), yOfGain),
          // Not shifted: the preamp cancels out of a difference.
          residual: pathOf(data.residual, yOfResidual),
          // Each band is drawn from the flat reference, so its distance from
          // that line is its contribution and those distances still sum to the
          // response's. Shifting each by the whole preamp would not.
          bands: data.bands.map((band) => pathOf(shifted(band, shift), yOfGain)),
          shift,
        }
      : {
          target: pathOf(shifted(data.target, shift), yOfGain),
          response: null,
          residual: null,
          bands: [],
          shift,
        };
  pathCache.set(offset, built);
  return built;
}

/** The nearest *visible* grid index to a frequency, for the hover readout. */
export function nearestIndex(hz: number): number {
  let best = VISIBLE_FROM;
  let bestGap = Infinity;
  meta.gridHz.forEach((point, i) => {
    if (i < VISIBLE_FROM) {
      return;
    }
    const gap = Math.abs(Math.log10(point) - Math.log10(hz));
    if (gap < bestGap) {
      bestGap = gap;
      best = i;
    }
  });
  return best;
}

/** Frequency at a horizontal position, inverting xOf. */
export function hzAt(x: number): number {
  const t = (x - MARGIN.left) / PLOT_WIDTH;
  return 10 ** (LOG_MIN + Math.min(1, Math.max(0, t)) * (LOG_MAX - LOG_MIN));
}

export type { Paths };
