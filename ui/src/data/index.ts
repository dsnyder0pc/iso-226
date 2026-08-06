/**
 * The generated data, and everything the UI knows about it.
 *
 * Both files are imported straight from `web/` -- the same bytes the Flask API
 * serves -- so there is no copy in this tree that could go stale. The two are
 * written by one run of `precompute_presets.py` and `tests/test_curves.py`
 * fails if they ever come from different ones.
 *
 * No DSP happens here or anywhere else in the browser. Band curves were
 * evaluated by SciPy on the grid the optimizer fitted against; the only
 * arithmetic below is adding decibels and subtracting a target.
 */
import curvesJson from '../../../web/curves.json';
import presetsJson from '../../../web/presets.json';

import { parseRefusal } from './refusal';
import type {
  CurvesFile,
  LevelData,
  PresetEntry,
  PresetsFile,
  RefusedLevel,
  ServedLevel,
} from './types';

// The one place the untyped JSON imports (see json.d.ts) are given a shape.
const presetsFile = presetsJson as PresetsFile;
const curvesFile = curvesJson as CurvesFile;

/** Only full compensation is fitted into the shipped grid. */
export const SHIPPED_SCALE = 1.0;

/** Mirrors preset_key() in precompute_presets.py. Both files use it. */
export function presetKey(offset: number, scale: number = SHIPPED_SCALE): string {
  const sign = offset >= 0 ? '+' : '-';
  return `${sign}${Math.abs(offset)}|${scale.toFixed(2)}`;
}

function servableOffsets(): number[] {
  return Object.values(presetsFile.presets)
    .filter((entry) => !entry.refused)
    .map((entry) => entry.offset)
    .sort((a, b) => a - b);
}

const servable = servableOffsets();
const firstServable = servable[0];
const lastServable = servable[servable.length - 1];
if (firstServable === undefined || lastServable === undefined) {
  throw new Error('web/presets.json contains no servable presets');
}

export const meta = {
  isoEdition: presetsFile.iso_edition,
  generatedUtc: presetsFile.generated_utc,
  designFs: presetsFile.design_fs,
  nominalReferenceDb: presetsFile.nominal_reference_db,
  bandCount: presetsFile.band_count,
  equivalenceToleranceDb: presetsFile.equivalence_tolerance_db,
  gridHz: curvesFile.grid_hz,
  /** Half-open index range of the ISO-backed span; outside it the target is held flat. */
  inBand: curvesFile.in_band,
  /** What the UI offers. The grid is fitted wider than it can serve. */
  servable: { min: firstServable, max: lastServable },
  /** What was fitted, including the offsets that were then refused. */
  fitted: { min: presetsFile.offset_range_db[0], max: presetsFile.offset_range_db[1] },
} as const;

/**
 * What the mastering reference control accepts.
 *
 * Wider than the 72-85 dB window the offset equivalence was measured across —
 * the curve for a given offset is the same either way, it is the claim that
 * one ladder covers every reference that stops being backed by a measurement.
 * LevelControls says so when the reference leaves that window.
 */
export const REFERENCE_RANGE: [number, number] = [60, 100];

/** The two frequencies the ISO data stops at, for labelling the held regions. */
export const isoBandHz = {
  low: meta.gridHz[meta.inBand[0]] ?? 20,
  high: meta.gridHz[meta.inBand[1] - 1] ?? 12500,
};

function refusedLevel(offset: number, entry: PresetEntry, target: number[]): RefusedLevel {
  const reason = entry.reason ?? 'This level was fitted and refused.';
  const parsed = parseRefusal(reason);
  return {
    kind: 'refused',
    offset,
    reason,
    explanation: parsed.explanation,
    // The message is written at the nominal reference, so a suggested level
    // becomes a suggested offset, which is what the UI navigates by.
    suggestedLevelOffset:
      parsed.suggestedLevel === null
        ? null
        : parsed.suggestedLevel - presetsFile.nominal_reference_db,
    suggestedScale: parsed.suggestedScale,
    target,
  };
}

function sumBands(bands: number[][], points: number): number[] {
  const total = new Array<number>(points).fill(0);
  // Magnitudes multiply, so decibels add: this is the cascade response, not an
  // approximation of it.
  for (const band of bands) {
    band.forEach((db, i) => {
      total[i] = (total[i] ?? 0) + db;
    });
  }
  return total;
}

function build(offset: number): LevelData {
  const key = presetKey(offset);
  const entry = presetsFile.presets[key];
  const curve = curvesFile.curves[key];
  if (!entry || !curve) {
    return { kind: 'unknown', offset };
  }
  if (entry.refused) {
    return refusedLevel(offset, entry, curve.target);
  }
  const bands = curve.bands ?? [];
  const response = sumBands(bands, curve.target.length);
  const served: ServedLevel = {
    kind: 'served',
    offset,
    headroomDb: entry.headroom_db ?? 0,
    maxResidualDb: entry.max_residual_db ?? 0,
    targetMet: entry.target_met ?? true,
    filters: entry.filters ?? [],
    target: curve.target,
    bands,
    response,
    residual: response.map((db, i) => db - (curve.target[i] ?? 0)),
  };
  return served;
}

// Dragging the slider walks the whole ladder in a second or two. Each level is
// differenced once and then reused, so a return visit costs a map lookup.
const cache = new Map<number, LevelData>();

/** Everything known about one offset, computed at most once. */
export function levelData(offset: number): LevelData {
  const hit = cache.get(offset);
  if (hit) {
    return hit;
  }
  const built = build(offset);
  cache.set(offset, built);
  return built;
}

/** The offset a measured level implies. Presets exist at whole decibels only. */
export function offsetFor(level: number, reference: number): number {
  return Math.round(level - reference);
}
