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
          sits third so it lands under Headroom in the 2-up layout: it is that
          number with the midrange difference taken out, and the two are within
          a couple of tenths of each other, which reads as a typo unless they
          are next to each other with the note to explain it. */}
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
          note="Apply this attenuation to the unfiltered signal to compare. Both then sound the same size, so only the tone changes."
        />
        <Stat
          icon={<Sliders className="h-4 w-4" />}
          label="Bands"
          value={`${data.filters.length}`}
          note="Five exhaust the ISO target; a second tier changes less than the rounding."
        />
      </div>

      <p className="rounded-2xl border border-slate-800/80 bg-ink p-4 text-base leading-relaxed text-slate-400">
        The residual is measured on the <strong className="text-slate-200">published,
        rounded</strong> values in the table below — not on an unrounded fit behind
        them — and on the filter cascade alone, before the headroom adjustment.
      </p>

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
