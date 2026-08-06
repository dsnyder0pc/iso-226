/**
 * Reading the generator's refusal message.
 *
 * Pure and free of imports on purpose: `scripts/check-suggestions.ts` runs it
 * under Node against every refused preset and asserts that the level it comes
 * back with is one the grid can actually serve. That is the same rule
 * `test_every_suggested_level_can_actually_be_served` holds the HTTP API to.
 *
 * The message names a level twice — the one that failed, and the one to try
 * instead:
 *
 *     Cannot build a usable filter set for --level 58 --reference 83: ...
 *
 *     Try one of:
 *       --scale 0.85      apply partial compensation ...
 *       --level 62        target a higher listening level
 *
 * Only the second is a suggestion. Reading the first offers the user the level
 * that just failed, which is worse than offering nothing.
 */
const SUGGESTIONS_MARKER = 'Try one of:';

export interface Refusal {
  /** The headline, up to the list of alternatives. */
  explanation: string;
  /** A level the generator suggests, in dB at the nominal reference. */
  suggestedLevel: number | null;
  /** Partial compensation the CLI could apply. The shipped grid is scale 1.0 only. */
  suggestedScale: number | null;
}

export function parseRefusal(reason: string): Refusal {
  const marker = reason.indexOf(SUGGESTIONS_MARKER);
  const explanation = (marker === -1 ? reason : reason.slice(0, marker)).trim();
  const suggestions = marker === -1 ? '' : reason.slice(marker + SUGGESTIONS_MARKER.length);

  const level = /--level\s+(\d+(?:\.\d+)?)/.exec(suggestions);
  const scale = /--scale\s+(\d*\.?\d+)/.exec(suggestions);
  return {
    explanation,
    suggestedLevel: level?.[1] === undefined ? null : Number(level[1]),
    suggestedScale: scale?.[1] === undefined ? null : Number(scale[1]),
  };
}
