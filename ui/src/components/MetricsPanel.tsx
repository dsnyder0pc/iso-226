import type { ReactNode } from 'react';
import { ArrowLeftRight, CircleAlert, Gauge, Ruler, Sliders } from 'lucide-react';

import { isoBandHz, meta } from '../data';
import type { ServedLevel } from '../data/types';
import { fixed, formatOffset, publishedHz } from '../format';

interface Props {
  data: ServedLevel;
  level: number;
  reference: number;
}

export function MetricsPanel({ data, level, reference }: Props) {
  return (
    <section className="space-y-4 rounded-3xl border border-slate-800 bg-panel p-6 shadow-xl">
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
          Compensation for {level} dB from a master at {reference} dB
        </h2>
        <p className="mt-1 text-sm text-slate-400 sm:text-base">
          {formatOffset(data.offset)} offset · {data.filters.length} bands · full
          compensation · designed and analysed at {(meta.designFs / 1000).toFixed(1)} kHz ·{' '}
          {meta.isoEdition}
        </p>
      </div>

      {/* Four across on a wide window, two by two below that. The A/B figure
          sits third so it lands under Headroom in the 2-up layout: matched at
          1 kHz the two are the *same number* at every rung but the loosest,
          which reads as a duplicate unless they sit together with the note
          explaining that one is for the filtered side and one for the flat. */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat
          icon={<Gauge className="h-4 w-4" />}
          label="Headroom"
          value={`${fixed(data.headroomDb, 1)} dB`}
          note="Enter as preamp/headroom. Worst case across 44.1/48/96/192 kHz."
        />
        <Stat
          icon={<Ruler className="h-4 w-4" />}
          label="Max residual"
          value={`${data.maxResidualDb.toFixed(4)} dB`}
          note={`Worst deviation from the ISO target between ${publishedHz(isoBandHz.low)} and ${publishedHz(isoBandHz.high)} Hz.`}
        />
        <Stat
          icon={<ArrowLeftRight className="h-4 w-4" />}
          label="A/B bypass"
          value={`${fixed(data.bypassHeadroomDb, 1)} dB`}
          note="Play the unfiltered signal at this gain to compare. Matched at 1 kHz, so the midrange holds still and only the extremes change."
        />
        <Stat
          icon={<Sliders className="h-4 w-4" />}
          label="Bands"
          value={`${data.filters.length}`}
          note="Five exhaust the ISO target; a second tier changes less than the rounding."
        />
      </div>

      {/* The note on how the residual is measured used to sit here, which put
          the stat grid between the residual figure and its own explanation.
          It now lives under that figure. */}
      {!data.targetMet && (
        <p className="flex items-start gap-2 rounded-2xl border border-amber-500/30 bg-amber-500/10 p-4 text-base leading-relaxed text-amber-200">
          <CircleAlert className="mt-1 h-4 w-4 shrink-0" />
          Five bands could not reach the 0.05 dB accuracy target at this level.
          That is the honest limit of the band count, not a failed fit: the set
          below is the best of the search, and its real error is the figure
          quoted above.
        </p>
      )}
    </section>
  );
}

function Stat({
  icon,
  label,
  value,
  note,
}: {
  icon: ReactNode;
  label: string;
  value: string;
  note: string;
}) {
  return (
    <div className="rounded-2xl border border-slate-700/50 bg-inset p-4">
      <p className="flex items-center gap-1.5 text-sm font-semibold tracking-wider text-slate-400 uppercase">
        <span className="text-accent">{icon}</span>
        {label}
      </p>
      <p className="mt-1 font-mono text-3xl font-semibold text-white">{value}</p>
      <p className="mt-1.5 text-sm leading-snug text-slate-400">{note}</p>
    </div>
  );
}
