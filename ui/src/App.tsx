import type { ReactNode } from 'react';
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

const REPO_URL = 'https://github.com/dsnyder0pc/iso-226';

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
  const { playing, update, stop } = preview;
  useEffect(() => {
    if (!playing) {
      return;
    }
    if (data.kind === 'served') {
      update(data.filters, data.headroomDb);
    } else {
      // Landing on a refused level -- only reachable by typing a level or
      // following a link, since the slider stops at the servable range -- must
      // not leave the previous level's filters playing under a page that says
      // no filter set is served here.
      stop();
    }
  }, [data, playing, update, stop]);

  // The reference rung has no filters, and is still worth hearing: it is the
  // flat end of the comparison the bypass button makes at every other level.
  const togglePreview = () => {
    if (preview.playing) {
      preview.stop();
    } else if (data.kind === 'served') {
      preview.start(data.filters, data.headroomDb);
    }
  };

  return (
    <div className="min-h-screen pb-16 text-slate-100">
      <Header
        canPreview={data.kind === 'served'}
        playing={preview.playing}
        bypassed={preview.bypassed}
        sampleRate={preview.sampleRate}
        onTogglePreview={togglePreview}
        onToggleBypass={() => preview.setBypass(!preview.bypassed)}
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

        {/* The plot is told what is audible, not which buttons are pressed:
            "bypassed" only means anything while something is playing. */}
        <ResponsePlot
          data={data}
          hearing={
            !preview.playing ? null : preview.bypassed ? 'flat' : 'compensated'
          }
        />

        {data.kind === 'served' && data.filters.length > 0 && (
          <>
            <MetricsPanel data={data} level={level} reference={reference} />
            <FilterTable filters={data.filters} headroomDb={data.headroomDb} />
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
          <section className="rounded-3xl border border-slate-800 bg-panel p-6 text-base text-slate-400">
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
      <h2 className="text-xl font-semibold text-white">No compensation needed</h2>
      <p className="mt-2 text-base leading-relaxed text-slate-400">
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

/**
 * Opens in a new tab: leaving mid-comparison should not cost the level on
 * screen. `hash` addresses a section of the README, which GitHub renders at the
 * repository root.
 */
function RepoLink({ children, hash }: { children: ReactNode; hash?: string }) {
  return (
    <a
      href={hash ? `${REPO_URL}#${hash}` : REPO_URL}
      target="_blank"
      rel="noreferrer"
      className="text-slate-300 underline decoration-slate-600 underline-offset-2 hover:text-accent"
    >
      {children}
    </a>
  );
}

function FooterHeading({ children }: { children: ReactNode }) {
  return (
    <h2 className="mb-3 text-sm font-semibold tracking-widest text-slate-400 uppercase">
      {children}
    </h2>
  );
}

/**
 * The closing block: how to use the page, then what is worth knowing about the
 * numbers on it.
 *
 * Two short lists rather than four paragraphs. The full version of all of this
 * is in the README — see "Using the web app" there — and it belongs there
 * rather than here, because a listener reads this page to get a filter set out
 * of it, not to read about it.
 */
function Provenance() {
  return (
    <footer className="grid gap-x-10 gap-y-8 rounded-3xl border border-slate-800/70 bg-panel/50 p-6 text-base leading-relaxed text-slate-400 md:grid-cols-2">
      <section>
        <FooterHeading>How to use this page</FooterHeading>
        <ol className="ml-5 list-decimal space-y-2">
          <li>
            Measure your <strong className="text-slate-300">average</strong> level
            for one listening scenario — late at night, over dinner, sitting down
            to listen properly. An SPL meter app set to{' '}
            <strong className="text-slate-300">C-weighted, slow</strong> is enough.
          </li>
          <li>Move the slider to that level.</li>
          <li>
            Enter the headroom adjustment and the five filters into your player,
            or copy a ready-made config from Export above.
          </li>
          <li>Enable the filter and play music at that level.</li>
        </ol>
        <p className="mt-3">
          Repeat for your other scenarios. Two or three saved presets cover most
          listening.
        </p>
      </section>

      <section>
        <FooterHeading>Worth knowing</FooterHeading>
        <ul className="ml-5 list-disc space-y-2">
          <li>
            The level matters more than the filters. A 6 dB error there costs
            about 3.15 dB of correction; a measurement convention shared by the
            level and the reference cancels.
          </li>
          <li>
            Every curve and number here was computed by the Python that generates
            the presets in <RepoLink>the repository</RepoLink> and shipped with
            the page. The browser adds decibels and subtracts a target; it
            evaluates no filters.
          </li>
          <li>
            The README covers the rest:{' '}
            <RepoLink hash="using-the-web-app">using this page</RepoLink>,{' '}
            <RepoLink hash="how-to-work-out-your---level--and-why-it-is-easier-than-it-looks">
              measuring your level
            </RepoLink>
            , <RepoLink hash="why-five-bands">why five bands</RepoLink>, and{' '}
            <RepoLink hash="relationship-to-the-standard">
              what the standard does and does not vouch for
            </RepoLink>
            .
          </li>
        </ul>
      </section>

      <p className="font-mono text-sm md:col-span-2">
        {meta.isoEdition} · presets generated {meta.generatedUtc}
      </p>
    </footer>
  );
}
