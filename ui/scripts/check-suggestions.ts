/**
 * Every level the page offers instead of a refusal must be one it can serve.
 *
 * This is the UI's copy of the rule `test_every_suggested_level_can_actually_be_served`
 * holds the HTTP API to. It earns its place: the first version of the parser
 * matched the *first* `--level` in the refusal message, which is the level that
 * had just failed, so the page offered 58 dB as the way out of 58 dB being
 * unavailable.
 *
 *     npm run check:suggestions
 */
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { parseRefusal } from '../src/data/refusal';

const REPO = join(dirname(fileURLToPath(import.meta.url)), '..', '..');

interface Entry {
  offset: number;
  refused: boolean;
  reason?: string;
}

const presets = JSON.parse(readFileSync(join(REPO, 'web', 'presets.json'), 'utf8')) as {
  nominal_reference_db: number;
  presets: Record<string, Entry>;
};

const servable = new Set(
  Object.values(presets.presets)
    .filter((entry) => !entry.refused)
    .map((entry) => entry.offset),
);

const failures: string[] = [];
let checked = 0;

for (const [key, entry] of Object.entries(presets.presets)) {
  if (!entry.refused) {
    continue;
  }
  checked += 1;
  const { suggestedLevel, explanation } = parseRefusal(entry.reason ?? '');
  if (suggestedLevel === null) {
    failures.push(`${key}: refused with no level to suggest instead`);
    continue;
  }
  const offset = suggestedLevel - presets.nominal_reference_db;
  if (!servable.has(offset)) {
    failures.push(
      `${key}: suggests ${suggestedLevel} dB (offset ${offset}), which is not servable`,
    );
  }
  if (offset <= entry.offset) {
    failures.push(
      `${key}: suggests ${suggestedLevel} dB, no louder than the level that was refused`,
    );
  }
  if (explanation.length === 0) {
    failures.push(`${key}: refusal has no explanation to show`);
  }
}

if (failures.length > 0) {
  console.error(`Refusal suggestions are wrong:\n  ${failures.join('\n  ')}`);
  process.exit(1);
}

if (checked === 0) {
  console.error('No refused presets found; this check compared nothing.');
  process.exit(1);
}

console.log(`All ${checked} refusals suggest a level the grid can serve.`);
