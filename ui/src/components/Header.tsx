import { Activity, ArrowLeftRight, Volume2, VolumeX } from 'lucide-react';

import { ShareButton } from './ShareButton';

interface Props {
  canPreview: boolean;
  playing: boolean;
  bypassed: boolean;
  sampleRate: number | null;
  onTogglePreview: () => void;
  onToggleBypass: () => void;
  shareUrl: string;
  shareTitle: string;
}

export function Header({
  canPreview,
  playing,
  bypassed,
  sampleRate,
  onTogglePreview,
  onToggleBypass,
  shareUrl,
  shareTitle,
}: Props) {
  return (
    <header className="sticky top-0 z-30 border-b border-slate-800/80 bg-ink/90 px-4 py-4 backdrop-blur-md sm:px-8">
      <div className="mx-auto flex max-w-7xl flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-2xl border border-accent/40 bg-accent/20 text-accent">
            <Activity className="h-5 w-5" />
          </span>
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
              Equal-Loudness <span className="text-accent">Compensation EQ</span>
            </h1>
            {/* What the page is for, in the reader's terms. The standard, the
                band count and the fact that this is a static page are all still
                on the page — in the legend, the metrics and the footer — where
                someone who cares will look for them. */}
            <p className="mt-0.5 text-sm text-slate-400">
              Compensates for the natural loss of hearing sensitivity to bass and
              treble at lower listening levels
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {/* A nerd detail, and the first thing to go when the row gets tight. */}
          {playing && sampleRate && (
            <span className="hidden font-mono text-sm text-slate-400 sm:inline">
              preview at {(sampleRate / 1000).toFixed(1)} kHz
            </span>
          )}
          {/* The comparison is the point of listening at all, so the control
              for it appears next to the transport rather than in a panel. */}
          {playing && (
            <button
              type="button"
              onClick={onToggleBypass}
              aria-pressed={bypassed}
              className={`flex items-center gap-1.5 rounded-2xl border px-3.5 py-2 text-sm font-medium transition-colors ${
                bypassed
                  ? 'border-amber-500/40 bg-amber-500/20 text-amber-100'
                  : 'border-slate-800 bg-panel text-slate-300 hover:bg-slate-800/60 hover:text-white'
              }`}
              title="Compare against flat. The filters come out and the headroom stays, so the midrange holds still and only the tilt changes — the dotted reference line on the plot."
            >
              <ArrowLeftRight className="h-3.5 w-3.5" />
              {bypassed ? 'Filters off' : 'Filters on'}
            </button>
          )}
          <button
            type="button"
            onClick={onTogglePreview}
            // Stopping is always allowed. Gating this on `canPreview` alone
            // left the button disabled at a level that cannot be previewed,
            // with no way to silence what was already playing.
            disabled={!canPreview && !playing}
            className={`flex items-center gap-1.5 rounded-2xl border px-3.5 py-2 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${
              playing
                ? 'border-emerald-500/40 bg-emerald-500/20 text-emerald-200'
                : 'border-slate-800 bg-panel text-slate-300 hover:bg-slate-800/60 hover:text-white'
            }`}
            title="Pink noise through these filters. Approximate: the browser runs at its own sample rate and uses its own biquads."
          >
            {playing ? <VolumeX className="h-3.5 w-3.5" /> : <Volume2 className="h-3.5 w-3.5" />}
            {playing ? 'Stop preview' : 'Hear it'}
          </button>
          <ShareButton url={shareUrl} title={shareTitle} />
        </div>
      </div>
    </header>
  );
}
