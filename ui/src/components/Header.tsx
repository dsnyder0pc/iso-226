import { Activity, Volume2, VolumeX } from 'lucide-react';

import { meta } from '../data';

interface Props {
  canPreview: boolean;
  playing: boolean;
  sampleRate: number | null;
  onTogglePreview: () => void;
}

export function Header({ canPreview, playing, sampleRate, onTogglePreview }: Props) {
  return (
    <header className="sticky top-0 z-30 border-b border-slate-800/80 bg-ink/90 px-4 py-4 backdrop-blur-md sm:px-8">
      <div className="mx-auto flex max-w-7xl flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-2xl border border-accent/40 bg-accent/20 text-accent">
            <Activity className="h-5 w-5" />
          </span>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-white sm:text-2xl">
              Equal-Loudness <span className="text-accent">Compensation EQ</span>
            </h1>
            <p className="mt-0.5 text-xs text-slate-400">
              {meta.isoEdition} · {meta.bandCount} bands · precomputed, served as a
              static page
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {playing && sampleRate && (
            <span className="font-mono text-[11px] text-slate-500">
              preview at {(sampleRate / 1000).toFixed(1)} kHz
            </span>
          )}
          <button
            type="button"
            onClick={onTogglePreview}
            disabled={!canPreview}
            className={`flex items-center gap-1.5 rounded-2xl border px-3.5 py-2 text-xs font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${
              playing
                ? 'border-emerald-500/40 bg-emerald-500/20 text-emerald-200'
                : 'border-slate-800 bg-panel text-slate-300 hover:bg-slate-800/60 hover:text-white'
            }`}
            title="Pink noise through these filters. Approximate: the browser runs at its own sample rate and uses its own biquads."
          >
            {playing ? <VolumeX className="h-3.5 w-3.5" /> : <Volume2 className="h-3.5 w-3.5" />}
            {playing ? 'Stop preview' : 'Hear it'}
          </button>
        </div>
      </div>
    </header>
  );
}
