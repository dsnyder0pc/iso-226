/** The shapes of the two generated artifacts, and of what the UI makes of them. */

/**
 * Matched literally by the generator, by check.py's Markdown parser and by the
 * YAML writer. Changing a string here changes nothing on its own -- see the
 * filter-type invariant in CLAUDE.md.
 */
export type FilterType = 'Low Shelf' | 'Peak' | 'High Shelf';

export interface Filter {
  band: number;
  type: FilterType;
  frequency: number;
  gain: number;
  q: number;
}

/** One entry of web/presets.json. */
export interface PresetEntry {
  offset: number;
  scale: number;
  refused: boolean;
  headroom_db?: number;
  max_residual_db?: number;
  target_met?: boolean;
  filters?: Filter[];
  reason?: string;
}

export interface PresetsFile {
  generated_utc: string;
  iso_edition: string;
  band_count: number;
  design_fs: number;
  nominal_reference_db: number;
  offset_range_db: [number, number];
  scales: number[];
  equivalence_tolerance_db: number;
  presets: Record<string, PresetEntry>;
}

/** One entry of web/curves.json: dB at each point of the shared grid. */
export interface CurveEntry {
  target: number[];
  bands?: number[][];
}

export interface CurvesFile {
  generated_utc: string;
  design_fs: number;
  grid_hz: number[];
  /** Half-open [start, stop) index range where ISO data backs the target. */
  in_band: [number, number];
  curves: Record<string, CurveEntry>;
}

/** A level the presets cover, with its curves already differenced. */
export interface ServedLevel {
  kind: 'served';
  offset: number;
  headroomDb: number;
  maxResidualDb: number;
  targetMet: boolean;
  filters: Filter[];
  target: number[];
  bands: number[][];
  /** Sum of the band curves: the cascade response, exactly. */
  response: number[];
  /** response - target. What max_residual_db is the worst in-band value of. */
  residual: number[];
}

/** A level that was fitted, found to need more headroom than exists, and refused. */
export interface RefusedLevel {
  kind: 'refused';
  offset: number;
  /** The generator's own message, verbatim. */
  reason: string;
  /** The headline, up to the list of alternatives. */
  explanation: string;
  /** A servable level the generator suggests instead, if there is one. */
  suggestedLevelOffset: number | null;
  /** Partial compensation the CLI could apply. The shipped grid is scale 1.0 only. */
  suggestedScale: number | null;
  target: number[];
}

/** A level outside the fitted grid entirely. */
export interface UnknownLevel {
  kind: 'unknown';
  offset: number;
}

export type LevelData = ServedLevel | RefusedLevel | UnknownLevel;
