/** Number formatting, in one place so the plot, the table and the exports agree. */

/**
 * A frequency as the published tables print it.
 *
 * `_freq_str` in the generator: two decimals with trailing zeros trimmed, so
 * 9885.0 reads as `9885` and 71.28 keeps both places. Not `%g`, which would
 * reach for exponential notation at 12 kHz — inside our range.
 */
export function publishedHz(hz: number): string {
  return hz.toFixed(2).replace(/0+$/, '').replace(/\.$/, '');
}

/**
 * `toFixed`, keeping the sign of a negative zero the way Python does.
 *
 * A band that rounds to a hair below zero is published as `-0.00` in the
 * tables and `-0.0` in the CamillaDSP configs — band 3 of the 80 dB preset is
 * one. JavaScript drops that sign, so the export would not match the file it
 * claims to reproduce.
 */
export function fixed(value: number, decimals: number): string {
  return `${Object.is(value, -0) ? '-' : ''}${value.toFixed(decimals)}`;
}

/** Signed decibels, for anything a reader might mistake for an absolute level. */
export function formatSigned(db: number, decimals = 2): string {
  return db > 0 ? `+${fixed(db, decimals)}` : fixed(db, decimals);
}

/** A listening-level offset, always signed: +0 dB is a statement, 0 dB is not. */
export function formatOffset(offset: number): string {
  return `${offset >= 0 ? '+' : ''}${offset} dB`;
}
