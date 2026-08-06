import { useState } from 'react';
import { ChevronDown, TriangleAlert } from 'lucide-react';

import { meta } from '../data';
import type { RefusedLevel } from '../data/types';
import { formatOffset } from '../format';

interface Props {
  data: RefusedLevel;
  reference: number;
  onLevel: (level: number) => void;
}

/**
 * A level that was fitted and then refused.
 *
 * The grid is fitted wider than it can serve, so a refusal is a real answer
 * with a reason attached, not a range error. The suggestion the generator
 * emits is deliberately conservative — it is estimated from the size of the
 * target rather than from a fit — so every level offered here is one that
 * actually works.
 */
export function RefusalNotice({ data, reference, onLevel }: Props) {
  const [showRaw, setShowRaw] = useState(false);
  const suggested =
    data.suggestedLevelOffset === null ? null : reference + data.suggestedLevelOffset;

  return (
    <section className="space-y-4 rounded-3xl border border-amber-500/30 bg-amber-500/5 p-6">
      <h2 className="flex items-center gap-2 text-sm font-semibold text-amber-200">
        <TriangleAlert className="h-4 w-4" />
        No filter set is served at {formatOffset(data.offset)}
      </h2>

      <p className="text-sm leading-relaxed text-slate-300">{data.explanation}</p>

      <div className="flex flex-wrap items-center gap-3">
        {suggested !== null && (
          <button
            type="button"
            onClick={() => onLevel(suggested)}
            className="rounded-xl border border-accent/40 bg-accent/20 px-4 py-2 text-sm font-semibold text-indigo-100 hover:bg-accent/30"
          >
            Use {suggested} dB instead
          </button>
        )}
        {data.suggestedScale !== null && (
          <p className="text-xs text-slate-400">
            The command-line generator can also apply partial compensation at
            this level —{' '}
            <code className="rounded bg-ink px-1.5 py-0.5 font-mono text-slate-300">
              --scale {data.suggestedScale}
            </code>
            . Only full compensation is precomputed here.
          </p>
        )}
      </div>

      <p className="text-xs leading-relaxed text-slate-500">
        Levels from {meta.servable.min + reference} dB up are served. Below that
        the fitted cascade needs more gain than a host’s ±12 dB band control
        provides, so the preset is withheld rather than clipped into shape.
      </p>

      <div>
        <button
          type="button"
          onClick={() => setShowRaw((open) => !open)}
          className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-300"
          aria-expanded={showRaw}
        >
          <ChevronDown
            className={`h-3 w-3 transition-transform ${showRaw ? 'rotate-180' : ''}`}
          />
          {showRaw ? 'Hide' : 'Show'} the generator’s message
        </button>
        {showRaw && (
          <pre className="mt-2 overflow-x-auto rounded-xl border border-slate-800 bg-ink p-3 font-mono text-[11px] leading-relaxed whitespace-pre-wrap text-slate-400">
            {data.reason}
          </pre>
        )}
      </div>
    </section>
  );
}
