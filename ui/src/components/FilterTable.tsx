import { Table } from 'lucide-react';

import type { Filter } from '../data/types';
import { fixed, formatSigned, publishedHz } from '../format';

/**
 * The five bands, with the preamp echoed beside the heading.
 *
 * The headroom has its own tile in the metrics panel, and that is still where
 * it is explained. It is repeated here because this panel is the one people
 * copy from, and a table of gains reaching +12 dB reads as a proposal to boost
 * until you know that -11.9 dB of preamp comes with it. A reviewer read it
 * exactly that way and called the shelves heavy-handed; the net at 20 Hz is
 * +0.10 dB. Echoed on the heading line rather than as a sixth column, which
 * would repeat one constant down five rows.
 */
export function FilterTable({
  filters,
  headroomDb,
}: {
  filters: Filter[];
  headroomDb: number;
}) {
  return (
    <section className="rounded-3xl border border-slate-800 bg-panel p-6 shadow-xl">
      <header className="mb-4 flex flex-wrap items-center justify-between gap-x-4 gap-y-1">
        <h2 className="flex items-center gap-2 text-sm font-semibold tracking-widest text-slate-400 uppercase">
          <Table className="h-4 w-4 text-accent" />
          Biquad filter specifications
        </h2>
        <p className="font-mono text-sm text-slate-400">
          preamp <span className="text-slate-200">{fixed(headroomDb, 1)} dB</span>
        </p>
      </header>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[38rem] border-collapse text-base">
          <thead>
            <tr className="border-b border-slate-700 text-left font-mono text-sm tracking-wider text-slate-400 uppercase">
              <th scope="col" className="py-2.5 pr-4 font-medium">Band</th>
              <th scope="col" className="py-2.5 pr-4 font-medium">Type</th>
              <th scope="col" className="py-2.5 pr-4 text-right font-medium">Frequency (Hz)</th>
              <th scope="col" className="py-2.5 pr-4 text-right font-medium">Gain (dB)</th>
              <th scope="col" className="py-2.5 text-right font-medium">Q</th>
            </tr>
          </thead>
          <tbody className="font-mono text-slate-200">
            {filters.map((filter) => (
              <tr key={filter.band} className="border-b border-slate-800/70 last:border-0">
                <td className="py-2.5 pr-4 text-slate-500">{filter.band}</td>
                <td className="py-2.5 pr-4 font-sans text-slate-300">{filter.type}</td>
                <td className="py-2.5 pr-4 text-right">{publishedHz(filter.frequency)}</td>
                <td
                  className={`py-2.5 pr-4 text-right ${
                    filter.gain >= 0 ? 'text-emerald-300' : 'text-sky-300'
                  }`}
                >
                  {formatSigned(filter.gain)}
                </td>
                <td className="py-2.5 text-right">{filter.q.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-4 text-base leading-relaxed text-slate-400">
        Enter these values as they appear, <strong className="text-slate-300">and
        the preamp with them</strong> — the bands lift the extremes, and without
        that much headroom a player with none of its own will clip. Frequency is
        given to four significant figures and Q to two decimals because that is
        what changes the response — a host that echoes back fewer digits than you
        typed is still storing what you typed.
      </p>
    </section>
  );
}
