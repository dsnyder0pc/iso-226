import { useEffect, useMemo, useState } from 'react';

import { Header } from './components/Header';
import { LevelControls } from './components/LevelControls';
import { MetricsPanel } from './components/MetricsPanel';
import { FilterTable } from './components/FilterTable';
import { ResponsePlot } from './components/ResponsePlot';
import { RefusalNotice } from './components/RefusalNotice';
import { ExportPanel } from './components/ExportPanel';
import { useAudioPreview } from './audio/useAudioPreview';
import { REFERENCE_RANGE, levelData, meta, offsetFor } from './data';
import { formatOffset } from './format';
import type { Bounds } from './url';
import { listeningQuery, readListening, shareUrl } from './url';

const DEFAULT_OFFSET = -15;

const URL_BOUNDS: Bounds = {
  reference: REFERENCE_RANGE,
  // The fitted range, not the servable one: a refusal is worth linking to.
  offset: [meta.fitted.min, meta.fitted.max],
};

// Dragging the slider fires a change per decibel. Safari throttles
// replaceState to 100 calls per 30 s, so settle before writing.
const URL_WRITE_DELAY_MS = 250;

export default function App() {
  const [initial] = useState(() =>
    readListening(
      window.location.search,
      { reference: meta.nominalReferenceDb, offset: DEFAULT_OFFSET },
      URL_BOUNDS,
    ),
  );
  const [reference, setReference] = useState(initial.reference);
  const [level, setLevel] = useState(initial.level);

  const offset = offsetFor(level, reference);

  // Keep the address bar on the level being looked at, so it can be copied,
  // bookmarked or reloaded. replaceState rather than pushState: a slider is
  // not thirty entries of browser history.
  useEffect(() => {
    const timer = window.setTimeout(() => {
      try {
        window.history.replaceState(null, '', `?${listeningQuery({ level, reference })}`);
      } catch {
        // Some embeddings forbid it. The page works; only the link goes stale.
      }
    }, URL_WRITE_DELAY_MS);
    return () => window.clearTimeout(timer);
  }, [level, reference]);

  const data = useMemo(() => levelData(offset), [offset]);
  const preview = useAudioPreview();

  // Keep a running preview on the level under the cursor. Depends on the two
  // stable pieces of the hook rather than the object it returns, which is new
  // on every render.
  const { playing, update } = preview;
  useEffect(() => {
    if (playing && data.kind === 'served') {
      update(data.filters, data.headroomDb);
    }
  }, [data, playing, update]);

  const togglePreview = () => {
    if (preview.playing) {
      preview.stop();
    } else if (data.kind === 'served' && data.filters.length > 0) {
      preview.start(data.filters, data.headroomDb);
    }
  };

  return (
    <div className="min-h-screen pb-16 text-slate-100">
      <Header
        canPreview={data.kind === 'served' && data.filters.length > 0}
        playing={preview.playing}
        sampleRate={preview.sampleRate}
        onTogglePreview={togglePreview}
        shareUrl={shareUrl(
          `${window.location.origin}${window.location.pathname}`,
          { level, reference },
        )}
        shareTitle={`Equal-loudness compensation for ${level} dB`}
      />

      <main className="mx-auto max-w-7xl space-y-6 px-4 pt-6 sm:px-6 lg:px-8">
        <LevelControls
          level={level}
          reference={reference}
          offset={offset}
          onLevel={setLevel}
          onReference={setReference}
          onReset={() => {
            setReference(meta.nominalReferenceDb);
            setLevel(meta.nominalReferenceDb + DEFAULT_OFFSET);
          }}
        />

        <ResponsePlot data={data} />

        {data.kind === 'served' && data.filters.length > 0 && (
          <>
            <MetricsPanel data={data} level={level} reference={reference} />
            <FilterTable filters={data.filters} />
            <ExportPanel
              context={{
                data,
                level,
                reference,
                designFs: meta.designFs,
                isoEdition: meta.isoEdition,
                nominalReferenceDb: meta.nominalReferenceDb,
              }}
            />
          </>
        )}

        {data.kind === 'served' && data.filters.length === 0 && <NoCorrectionNeeded />}

        {data.kind === 'refused' && (
          <RefusalNotice data={data} reference={reference} onLevel={setLevel} />
        )}

        {data.kind === 'unknown' && (
          <section className="rounded-3xl border border-slate-800 bg-panel p-6 text-sm text-slate-400">
            Nothing was fitted for an offset of {formatOffset(offset)}. The grid
            covers {formatOffset(meta.fitted.min)} to {formatOffset(meta.fitted.max)}.
          </section>
        )}

        <Provenance />
      </main>
    </div>
  );
}

function NoCorrectionNeeded() {
  return (
    <section className="rounded-3xl border border-slate-800 bg-panel p-6">
      <h2 className="text-lg font-semibold text-white">No compensation needed</h2>
      <p className="mt-2 text-sm leading-relaxed text-slate-400">
        You are listening at the level this recording was mastered for, so the
        ideal correction is 0.00 dB at every frequency.{' '}
        <strong className="text-slate-200">Apply no filters and no headroom
        adjustment.</strong>{' '}
        If a preset from another listening level is loaded, disable it — reaching
        for the nearest rung instead would apply about 1.6 dB of correction you do
        not want.
      </p>
    </section>
  );
}

function Provenance() {
  return (
    <footer className="rounded-3xl border border-slate-800/70 bg-panel/50 p-6 text-[11px] leading-relaxed text-slate-500">
      <p>
        Every curve and number on this page was computed by the same Python that
        generates the presets in the repository, and shipped with it. The browser
        adds decibels and subtracts a target; it evaluates no filters and
        interpolates no levels. Presets exist at whole-decibel offsets, so the
        slider steps in whole decibels.
      </p>
      <p className="mt-2">
        Measure the listening level broadband, C-weighted, slow. A measurement
        convention shared by the level and the reference cancels; an error in the
        level alone does not — 6 dB there costs about 3.15 dB of correction.
      </p>
      <p className="mt-2 font-mono">
        {meta.isoEdition} · presets generated {meta.generatedUtc}
      </p>
    </footer>
  );
}
