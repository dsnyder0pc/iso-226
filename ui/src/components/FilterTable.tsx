import { Table } from 'lucide-react';

import type { Filter } from '../data/types';
import { formatSigned, publishedHz } from '../format';

export function FilterTable({ filters }: { filters: Filter[] }) {
  return (
    <section className="rounded-3xl border border-slate-800 bg-panel p-6 shadow-xl">
      <h2 className="mb-4 flex items-center gap-2 text-xs font-semibold tracking-widest text-slate-400 uppercase">
        <Table className="h-4 w-4 text-accent" />
        Biquad filter specifications
      </h2>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[34rem] border-collapse text-sm">
          <thead>
            <tr className="border-b border-slate-700 text-left font-mono text-[11px] tracking-wider text-slate-400 uppercase">
              <th scope="col" className="py-2 pr-4 font-medium">Band</th>
              <th scope="col" className="py-2 pr-4 font-medium">Type</th>
              <th scope="col" className="py-2 pr-4 text-right font-medium">Frequency (Hz)</th>
              <th scope="col" className="py-2 pr-4 text-right font-medium">Gain (dB)</th>
              <th scope="col" className="py-2 text-right font-medium">Q</th>
            </tr>
          </thead>
          <tbody className="font-mono text-slate-200">
            {filters.map((filter) => (
              <tr key={filter.band} className="border-b border-slate-800/70 last:border-0">
                <td className="py-2 pr-4 text-slate-500">{filter.band}</td>
                <td className="py-2 pr-4 font-sans text-slate-300">{filter.type}</td>
                <td className="py-2 pr-4 text-right">{publishedHz(filter.frequency)}</td>
                <td
                  className={`py-2 pr-4 text-right ${
                    filter.gain >= 0 ? 'text-emerald-300' : 'text-sky-300'
                  }`}
                >
                  {formatSigned(filter.gain)}
                </td>
                <td className="py-2 text-right">{filter.q.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-4 text-[11px] leading-relaxed text-slate-500">
        Enter these values as they appear. Frequency is given to four significant
        figures and Q to two decimals because that is what changes the response —
        a host that echoes back fewer digits than you typed is still storing what
        you typed.
      </p>
    </section>
  );
}
