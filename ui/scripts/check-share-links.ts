/**
 * A shared link must reopen the page on the level it was shared from.
 *
 * Round-trips every servable level, and every refused one, through
 * `listeningQuery` and back through `readListening`. Then checks that a
 * hostile or malformed query falls back to the defaults instead of producing
 * a state the controls could not have reached.
 *
 *     npm run check:share-links
 */
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import type { Bounds, Listening } from '../src/url';
import { listeningQuery, readListening } from '../src/url';

const REPO = join(dirname(fileURLToPath(import.meta.url)), '..', '..');

const presets = JSON.parse(readFileSync(join(REPO, 'web', 'presets.json'), 'utf8')) as {
  nominal_reference_db: number;
  offset_range_db: [number, number];
  presets: Record<string, { offset: number }>;
};

const NOMINAL = presets.nominal_reference_db;
const DEFAULTS = { reference: NOMINAL, offset: -15 };
const BOUNDS: Bounds = { reference: [60, 100], offset: presets.offset_range_db };

const failures: string[] = [];

function roundTrips(state: Listening, note: string): void {
  const back = readListening(`?${listeningQuery(state)}`, DEFAULTS, BOUNDS);
  if (back.level !== state.level || back.reference !== state.reference) {
    failures.push(
      `${note}: shared ${state.level}/${state.reference} dB, reopened ` +
        `${back.level}/${back.reference} dB`,
    );
  }
}

// Every level in the grid, at the nominal reference and at both ends of what
// the reference control accepts.
let checked = 0;
for (const entry of Object.values(presets.presets)) {
  for (const reference of [NOMINAL, 72, 85]) {
    roundTrips({ level: reference + entry.offset, reference }, `offset ${entry.offset}`);
    checked += 1;
  }
}

// A measured level is not obliged to be a whole number.
roundTrips({ level: 68.5, reference: NOMINAL }, 'fractional level');

const rejected: [string, string][] = [
  ['', 'no query at all'],
  ['?level=abc&reference=83', 'unparseable level'],
  ['?level=68&reference=nonsense', 'unparseable reference'],
  ['?level=1e9&reference=83', 'level far outside the fitted grid'],
  ['?level=68&reference=5000', 'reference outside what the control accepts'],
  ['?level=&reference=', 'empty values'],
  ['?level=NaN&reference=NaN', 'NaN'],
];

for (const [query, note] of rejected) {
  const back = readListening(query, DEFAULTS, BOUNDS);
  const offset = back.level - back.reference;
  if (back.reference < BOUNDS.reference[0] || back.reference > BOUNDS.reference[1]) {
    failures.push(`${note}: produced reference ${back.reference} dB`);
  }
  if (offset < BOUNDS.offset[0] || offset > BOUNDS.offset[1]) {
    failures.push(`${note}: produced an offset of ${offset} dB, outside the fitted grid`);
  }
  if (!Number.isFinite(back.level) || !Number.isFinite(back.reference)) {
    failures.push(`${note}: produced ${back.level}/${back.reference}`);
  }
}

if (failures.length > 0) {
  console.error(`Share links do not round-trip:\n  ${failures.join('\n  ')}`);
  process.exit(1);
}

console.log(
  `${checked} shared levels reopen where they were shared from; ` +
    `${rejected.length} malformed queries fall back cleanly.`,
);
