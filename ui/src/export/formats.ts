/**
 * The published values in the shapes hosts accept.
 *
 * The CamillaDSP emitter reproduces `write_camilladsp_yaml` in
 * `loudness-filters.py` exactly -- `npm run check:exports` diffs its output
 * against the committed `REW/*.yml` and fails on any difference, because this
 * is the one place in the UI that reimplements a repository format rather than
 * reading one.
 *
 * No DOM here: the check script imports this module under Node.
 */
import type { Filter, FilterType, ServedLevel } from '../data/types';
import { fixed, publishedHz } from '../format';

export type ExportFormat = 'camilladsp' | 'apo' | 'roon' | 'csv' | 'json';

export interface ExportContext {
  data: ServedLevel;
  level: number;
  reference: number;
  designFs: number;
  isoEdition: string;
  /** The reference the shipped grid was fitted at. */
  nominalReferenceDb: number;
}

const CAMILLA_TYPE: Record<FilterType, string> = {
  'Low Shelf': 'Lowshelf',
  'High Shelf': 'Highshelf',
  Peak: 'Peaking',
};

const APO_TYPE: Record<FilterType, string> = {
  'Low Shelf': 'LSC',
  'High Shelf': 'HSC',
  Peak: 'PK',
};

/** Python's str() for a float: an integral value keeps one decimal place. */
function pyFloat(value: number): string {
  return Number.isInteger(value) ? fixed(value, 1) : String(value);
}

/**
 * Levels and references in header text.
 *
 * The generator prints these with `_level_str` and `{:g}` respectively, both
 * of which drop a trailing `.0`; JavaScript's default number-to-string does
 * the same thing, so one function covers both.
 */
function levelStr(value: number): string {
  return String(value);
}

function camilladsp(ctx: ExportContext): string {
  const { data } = ctx;
  const isDefault = ctx.reference === ctx.nominalReferenceDb;
  const header = [
    `# Equal-Loudness Compensation EQ for ${levelStr(ctx.level)} dB`,
    `# Mastering reference: ${levelStr(ctx.reference)} dB${isDefault ? '  (default)' : ''}` +
      ` · listening level: ${levelStr(ctx.level)} dB · scale: 1.00`,
    `# Headroom adjustment: ${data.headroomDb.toFixed(1)} dB (apply as negative preamp gain)`,
    `# Designed at ${(ctx.designFs / 1000).toFixed(1)} kHz.`,
    `# ${data.filters.length} bands, max residual error ` +
      `${data.maxResidualDb.toFixed(4)} dB against the ideal ISO 226 target.`,
    '',
  ];
  const body = ['filters:'];
  data.filters.forEach((filter, i) => {
    body.push(
      `  band_${i + 1}:`,
      '    type: Biquad',
      '    parameters:',
      `      type: ${CAMILLA_TYPE[filter.type]}`,
      `      freq: ${pyFloat(filter.frequency)}`,
      `      gain: ${pyFloat(filter.gain)}`,
      `      q: ${pyFloat(filter.q)}`,
    );
  });
  return `${header.join('\n')}${body.join('\n')}\n`;
}

function apo(ctx: ExportContext): string {
  const lines = [
    `# Equal-Loudness Compensation EQ for ${levelStr(ctx.level)} dB`,
    `# Mastering reference ${levelStr(ctx.reference)} dB · ${ctx.isoEdition}`,
    `Preamp: ${ctx.data.headroomDb.toFixed(1)} dB`,
  ];
  ctx.data.filters.forEach((filter, i) => {
    lines.push(
      `Filter ${i + 1}: ON ${APO_TYPE[filter.type]} Fc ${publishedHz(filter.frequency)} Hz ` +
        `Gain ${fixed(filter.gain, 2)} dB Q ${fixed(filter.q, 2)}`,
    );
  });
  return `${lines.join('\n')}\n`;
}

function roon(ctx: ExportContext): string {
  const lines = [
    `Equal-Loudness Compensation EQ for ${levelStr(ctx.level)} dB ` +
      `(mastering reference ${levelStr(ctx.reference)} dB)`,
    '',
    `Headroom / preamp: ${ctx.data.headroomDb.toFixed(1)} dB`,
    '',
    'Band  Type        Frequency (Hz)  Gain (dB)  Q',
  ];
  ctx.data.filters.forEach((filter) => {
    lines.push(
      `${String(filter.band).padEnd(6)}${filter.type.padEnd(12)}` +
        `${publishedHz(filter.frequency).padEnd(16)}` +
        `${fixed(filter.gain, 2).padEnd(11)}${fixed(filter.q, 2)}`,
    );
  });
  lines.push(
    '',
    `Max residual error ${ctx.data.maxResidualDb.toFixed(4)} dB against the ideal ISO 226 target.`,
  );
  return `${lines.join('\n')}\n`;
}

function csv(ctx: ExportContext): string {
  const rows = ['band,type,frequency_hz,gain_db,q'];
  ctx.data.filters.forEach((filter: Filter) => {
    rows.push(
      `${filter.band},${filter.type},${publishedHz(filter.frequency)},` +
        `${fixed(filter.gain, 2)},${fixed(filter.q, 2)}`,
    );
  });
  return `${rows.join('\n')}\n`;
}

function json(ctx: ExportContext): string {
  return `${JSON.stringify(
    {
      iso_edition: ctx.isoEdition,
      level_db: ctx.level,
      reference_db: ctx.reference,
      offset_db: ctx.data.offset,
      scale: 1.0,
      design_fs: ctx.designFs,
      headroom_db: ctx.data.headroomDb,
      max_residual_db: ctx.data.maxResidualDb,
      filters: ctx.data.filters,
    },
    null,
    2,
  )}\n`;
}

const EMITTERS: Record<ExportFormat, (ctx: ExportContext) => string> = {
  camilladsp,
  apo,
  roon,
  csv,
  json,
};

export const FORMAT_LABELS: Record<ExportFormat, { name: string; extension: string; note: string }> =
  {
    camilladsp: {
      name: 'CamillaDSP',
      extension: 'yml',
      note: 'Byte-identical to the REW/ configs in the repository.',
    },
    apo: { name: 'Equalizer APO', extension: 'txt', note: 'Also read by AutoEQ tooling.' },
    roon: { name: 'Roon', extension: 'txt', note: 'For typing into Roon’s Parametric EQ.' },
    csv: { name: 'CSV', extension: 'csv', note: 'For a spreadsheet or a script.' },
    json: { name: 'JSON', extension: 'json', note: 'The same fields the HTTP API returns.' },
  };

export function render(format: ExportFormat, ctx: ExportContext): string {
  return EMITTERS[format](ctx);
}

export function filename(format: ExportFormat, ctx: ExportContext): string {
  const stem = `filter_${levelStr(ctx.reference)}_to_${levelStr(ctx.level)}_s1.0`;
  return `${stem}.${FORMAT_LABELS[format].extension}`;
}
