/**
 * The page's state as a link.
 *
 * The two parameters are `level` and `reference` — the same names, and the
 * same meanings, that `/v1/filters` takes. A reader who knows one knows the
 * other, and a shared link translates to a curl command by inspection.
 *
 * A link carries both numbers verbatim rather than the offset that actually
 * keys the data. The offset is the more useful number to the code and the less
 * meaningful one to a listener, and sending it would silently re-target a
 * shared link at whatever reference the recipient happens to have set. Sending
 * both says what the sender was looking at and lets the recipient change it.
 *
 * Pure and import-free, so `scripts/check-share-links.ts` can round-trip it
 * under Node.
 */
export interface Listening {
  level: number;
  reference: number;
}

export interface Bounds {
  /** What the mastering reference control accepts. */
  reference: [number, number];
  /** The fitted offset range — wider than the servable one, so a refusal is shareable. */
  offset: [number, number];
}

function within(value: number, [low, high]: [number, number]): boolean {
  return Number.isFinite(value) && value >= low && value <= high;
}

function parse(params: URLSearchParams, name: string): number | null {
  const raw = params.get(name);
  if (raw === null || raw.trim() === '') {
    return null;
  }
  const value = Number(raw);
  return Number.isFinite(value) ? value : null;
}

/**
 * Read a link's state, falling back per field rather than wholesale.
 *
 * A parameter that is missing, unparseable or outside what the controls
 * themselves allow is ignored. Clamping it instead would hand the reader a
 * different level from the one the link names, without saying so.
 */
export function readListening(
  search: string,
  defaults: { reference: number; offset: number },
  bounds: Bounds,
): Listening {
  const params = new URLSearchParams(search);

  const askedReference = parse(params, 'reference');
  const reference =
    askedReference !== null && within(askedReference, bounds.reference)
      ? askedReference
      : defaults.reference;

  const askedLevel = parse(params, 'level');
  const level =
    askedLevel !== null && within(askedLevel - reference, bounds.offset)
      ? askedLevel
      : reference + defaults.offset;

  return { level, reference };
}

/** The query string for a state, without the leading `?`. */
export function listeningQuery({ level, reference }: Listening): string {
  return new URLSearchParams({
    level: String(level),
    reference: String(reference),
  }).toString();
}

/** An absolute link to a state, given the page's origin and path. */
export function shareUrl(base: string, state: Listening): string {
  return `${base}?${listeningQuery(state)}`;
}
