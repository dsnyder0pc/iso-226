/**
 * Hold the CamillaDSP emitter to the files the repository publishes.
 *
 * `src/export/formats.ts` is the only place the UI reimplements a repository
 * format instead of reading one, so it is the only place that can drift away
 * from `loudness-filters.py` without anything noticing. This diffs its output
 * against every committed `REW/*.yml` and exits non-zero on the first
 * character of difference.
 *
 * It is an npm script rather than a pytest test on purpose: someone working on
 * the maths should not need a JavaScript toolchain to run the Python suite,
 * the same reason Flask is absent from the root requirements.txt.
 *
 *     npm run check:exports
 */
import { readFileSync, readdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import type { Filter, ServedLevel } from '../src/data/types';
import { render } from '../src/export/formats';

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = join(HERE, '..', '..');

interface PresetEntry {
  offset: number;
  refused: boolean;
  headroom_db?: number;
  bypass_headroom_db?: number;
  max_residual_db?: number;
  filters?: Filter[];
}

interface PresetsFile {
  iso_edition: string;
  design_fs: number;
  nominal_reference_db: number;
  presets: Record<string, PresetEntry>;
}

// Read from disk rather than importing: this runs under Node, where a JSON
// import needs an import attribute the app's bundler does not use.
const presets = JSON.parse(
  readFileSync(join(REPO, 'web', 'presets.json'), 'utf8'),
) as PresetsFile;

function served(entry: PresetEntry): ServedLevel {
  return {
    kind: 'served',
    offset: entry.offset,
    headroomDb: entry.headroom_db ?? 0,
    bypassHeadroomDb: entry.bypass_headroom_db ?? 0,
    maxResidualDb: entry.max_residual_db ?? 0,
    targetMet: true,
    filters: entry.filters ?? [],
    target: [],
    bands: [],
    response: [],
    residual: [],
  };
}

let checked = 0;
const failures: string[] = [];

for (const name of readdirSync(join(REPO, 'REW')).sort()) {
  const match = /^filter_(\d+)_to_(\d+)_s1\.0\.yml$/.exec(name);
  const referenceText = match?.[1];
  const levelText = match?.[2];
  if (referenceText === undefined || levelText === undefined) {
    continue;
  }
  const reference = Number(referenceText);
  const level = Number(levelText);
  if (level === reference) {
    // The pass-through preset ships five zero-gain bands so the YAML stays a
    // loadable config; the API publishes it as no filters at all, and the UI
    // shows a sentence instead of an export. Nothing to compare.
    continue;
  }

  const key = `${level - reference >= 0 ? '+' : '-'}${Math.abs(level - reference)}|1.00`;
  const entry = presets.presets[key];
  if (!entry || entry.refused) {
    failures.push(`${name}: web/presets.json cannot serve ${key}`);
    continue;
  }

  const expected = readFileSync(join(REPO, 'REW', name), 'utf8');
  const actual = render('camilladsp', {
    data: served(entry),
    level,
    reference,
    designFs: presets.design_fs,
    isoEdition: presets.iso_edition,
    nominalReferenceDb: presets.nominal_reference_db,
  });

  if (actual !== expected) {
    failures.push(`${name}:\n${firstDifference(expected, actual)}`);
  }
  checked += 1;
}

function firstDifference(expected: string, actual: string): string {
  const want = expected.split('\n');
  const got = actual.split('\n');
  for (let i = 0; i < Math.max(want.length, got.length); i += 1) {
    if (want[i] !== got[i]) {
      return `  line ${i + 1}\n  repository: ${JSON.stringify(want[i])}\n  emitter:    ${JSON.stringify(got[i])}`;
    }
  }
  return '  files differ only in trailing content';
}

if (failures.length > 0) {
  console.error(`CamillaDSP export does not match the repository:\n\n${failures.join('\n\n')}`);
  process.exit(1);
}

if (checked < 10) {
  console.error(`Only ${checked} presets compared; expected the committed ladder.`);
  process.exit(1);
}

console.log(`CamillaDSP export matches all ${checked} committed REW/ configs.`);
