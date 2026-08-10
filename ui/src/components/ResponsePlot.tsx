import { Activity } from 'lucide-react';

import { isoBandHz, meta } from '../data';
import type { LevelData } from '../data/types';
import {
  WIDTH,
  frames,
  gainTicks,
  hzAt,
  nearestIndex,
  pathsFor,
  xOf,
  yOfGain,
} from '../plot/geometry';
import { publishedHz } from '../format';
import {
  FrequencyGrid,
  type Hearing,
  Key,
  Legend,
  LegendNote,
  PlotCard,
  PlotFrame,
  Readout,
} from './PlotParts';

interface Props {
  data: LevelData;
  hearing: Hearing;
  hover: number | null;
  onHover: (index: number | null) => void;
}

const HELD_HIGH_X = xOf(isoBandHz.high);

export function ResponsePlot({ data, hearing, hover, onHover }: Props) {
  const paths = pathsFor(data.offset);

  if (data.kind === 'unknown' || !paths) {
    return (
      <section className="rounded-3xl border border-slate-800 bg-panel p-6">
        <p className="text-base text-slate-400">
          No preset was fitted for this offset, so there is nothing to plot.
        </p>
      </section>
    );
  }

  const served = data.kind === 'served' ? data : null;
  const readout = hover === null ? null : readoutAt(data, hover, paths.shift);
  // Bypass takes the bands out and keeps the preamp, so what is audible then is
  // exactly the flat reference this plot already drew as a dotted line. Until
  // this prop existed the two were unconnected, and a reviewer toggling the
  // button heard the sound change while the picture sat still -- and concluded
  // he had misunderstood the page rather than that it had told him nothing.
  const flatIsLive = hearing === 'flat';

  return (
    <PlotCard
      icon={<Activity className="h-4 w-4" />}
      title="Frequency response"
      aside={
        <>
          {data.kind === 'served'
            ? `preamp ${data.headroomDb.toFixed(1)} dB applied`
            : `preamp ${paths.shift.toFixed(1)} dB required`}{' '}
          · evaluated at {(meta.designFs / 1000).toFixed(1)} kHz
        </>
      }
    >
      <PlotFrame>
        <svg
          viewBox={`0 0 ${WIDTH} ${frames.response.viewHeight}`}
          // pan-y, not none: the plot is a tall slab of a touch screen, and
          // touch-action: none there means a finger swiped over it cannot
          // scroll the page. Vertical drags stay with the browser; horizontal
          // ones still reach the crosshair.
          className="w-full touch-pan-y"
          role="img"
          aria-label={describe(data, hearing)}
          onPointerMove={(event) => {
            const box = event.currentTarget.getBoundingClientRect();
            onHover(nearestIndex(hzAt(((event.clientX - box.left) / box.width) * WIDTH)));
          }}
          onPointerLeave={() => onHover(null)}
          // A touch readout survives lifting the finger -- that is how you
          // read a value on a tablet -- but not the browser stealing the
          // gesture to scroll, which would strand the crosshair mid-page.
          onPointerCancel={() => onHover(null)}
        >
          {/* Above 12.5 kHz ISO has no data and the target is held flat; the
              filters are constrained there, never optimized there. The view
              starts at 20 Hz, so the matching region at the bottom is off the
              left edge rather than shaded. */}
          <rect
            x={HELD_HIGH_X}
            y={frames.response.top}
            width={frames.right - HELD_HIGH_X}
            height={frames.response.height}
            className="fill-slate-100/[0.035]"
          />

          <FrequencyGrid top={frames.response.top} bottom={frames.response.bottom} />

          {gainTicks().map((db) => (
            <g key={db}>
              <line
                x1={frames.left}
                y1={yOfGain(db)}
                x2={frames.right}
                y2={yOfGain(db)}
                className="stroke-slate-700/40"
                strokeWidth={1}
              />
              <text
                x={frames.left - 8}
                y={yOfGain(db) + 4}
                textAnchor="end"
                className="fill-slate-500 text-[11px]"
              >
                {db > 0 ? `+${db}` : db}
              </text>
            </g>
          ))}
          <text
            x={frames.left - 8}
            y={frames.response.top - 4}
            textAnchor="end"
            className="fill-slate-500 text-[10px]"
          >
            dB
          </text>

          {/* 0 dBFS. With the preamp applied the response sits below this, which
              is the whole point of publishing a headroom figure. */}
          <line
            x1={frames.left}
            y1={yOfGain(0)}
            x2={frames.right}
            y2={yOfGain(0)}
            className="stroke-rose-400/70"
            strokeWidth={1.25}
            strokeDasharray="6 4"
          />
          <text
            x={HELD_HIGH_X - 8}
            y={yOfGain(0) - 5}
            textAnchor="end"
            className="fill-rose-300/80 text-[10px]"
          >
            0 dBFS — clipping
          </text>

          {/* Where a band contributing nothing lands: the preamp itself, and
              so also what the bypass leaves audible. It becomes the solid
              trace while that is what is playing. */}
          <line
            x1={frames.left}
            y1={yOfGain(paths.shift)}
            x2={frames.right}
            y2={yOfGain(paths.shift)}
            className={flatIsLive ? 'stroke-slate-200' : 'stroke-slate-400/50'}
            strokeWidth={flatIsLive ? 2.5 : 1}
            strokeDasharray={flatIsLive ? undefined : '2 4'}
          />

          {/* Individual bands, behind everything they sum to. Out of circuit
              under bypass, so they fade with the sum they belong to. */}
          {paths.bands.map((d, i) => (
            <path
              key={i}
              d={d}
              fill="none"
              className={flatIsLive ? 'stroke-accent/10' : 'stroke-accent/25'}
              strokeWidth={1.25}
              strokeDasharray="3 3"
            />
          ))}

          {/* Warm and wide, under a cool and narrow response: the target is the
              band the achieved curve should sit inside, and it has to be told
              apart from that curve at a glance. */}
          <path
            d={paths.target}
            fill="none"
            className="stroke-target"
            strokeWidth={6}
            strokeLinejoin="round"
            opacity={0.5}
          />
          {paths.response && (
            <path
              d={paths.response}
              fill="none"
              className="stroke-accent"
              strokeWidth={2.25}
              strokeLinejoin="round"
              // Ghosted rather than hidden under bypass: the comparison is the
              // point, and a trace that vanished would read as the filters
              // having been unloaded rather than switched out of circuit.
              opacity={flatIsLive ? 0.3 : 1}
              strokeDasharray={flatIsLive ? '5 4' : undefined}
            />
          )}

          <text
            x={HELD_HIGH_X + 14}
            y={frames.response.top + 14}
            className="fill-slate-500 text-[10px]"
            textAnchor="end"
            transform={`rotate(-90 ${HELD_HIGH_X + 14} ${frames.response.top + 14})`}
          >
            held flat
          </text>

          {readout && (
            <g pointerEvents="none">
              <line
                x1={readout.x}
                y1={frames.response.top}
                x2={readout.x}
                y2={frames.response.bottom}
                className="stroke-slate-300/40"
                strokeWidth={1}
              />
              <circle
                cx={readout.x}
                cy={yOfGain(readout.target)}
                r={3}
                className="fill-target"
              />
              {readout.response !== null && (
                <circle
                  cx={readout.x}
                  cy={yOfGain(readout.response)}
                  r={3.5}
                  className="fill-accent"
                />
              )}
              <Readout
                x={readout.x}
                top={frames.response.top + 10}
                width={184}
                height={readout.response === null ? 46 : 64}
              >
                <text x={12} y={20} className="fill-slate-100 font-mono text-[11px]">
                  {publishedHz(readout.hz)} Hz
                </text>
                <text x={12} y={38} className="fill-target font-mono text-[11px]">
                  target {readout.target.toFixed(2)} dB
                </text>
                {readout.response !== null && (
                  <text x={12} y={56} className="fill-accent font-mono text-[11px]">
                    achieved {readout.response.toFixed(2)} dB
                  </text>
                )}
              </Readout>
            </g>
          )}
        </svg>
      </PlotFrame>

      <Legend>
        {/* What is playing belongs among the keys: it names one of the traces
            beside it, and it is the one drawn solid while it is playing. Only
            while the preview runs -- on a silent page there is nothing being
            heard, and a chip claiming otherwise would be furniture. Everything
            in this row is below the figure, so it may appear, disappear and
            rewrap without moving the plot. */}
        {hearing !== null && (
          <span
            className={`flex items-center gap-1.5 rounded-full border px-3 py-1 font-medium ${
              flatIsLive
                ? 'border-slate-400/40 bg-slate-400/15 text-slate-100'
                : 'border-accent/40 bg-accent/15 text-accent'
            }`}
          >
            <span
              className={`inline-block h-0.5 w-5 rounded-full ${
                flatIsLive ? 'bg-slate-200' : 'bg-accent'
              }`}
            />
            Hearing {flatIsLive ? 'flat — filters off' : 'the compensated response'}
          </span>
        )}
        <Key className="bg-target/70" label={`ISO ${meta.isoEdition.slice(4)} target`} />
        {served && (
          <Key
            className="bg-accent"
            label={flatIsLive ? 'Achieved (switched out)' : 'Achieved (published values)'}
          />
        )}
        {served && <Key className="bg-accent/30" label="Individual bands" />}
        <Key className="bg-rose-400/70" label="0 dBFS" />
        <Key
          className={flatIsLive ? 'bg-slate-200' : 'bg-slate-400/50'}
          label={flatIsLive ? 'Flat reference (playing now)' : 'Flat reference (the preamp)'}
        />
        <LegendNote>
          Both traces include the preamp, so 0 dBFS is the clipping limit they stay
          under. {publishedHz(isoBandHz.low)}–{publishedHz(isoBandHz.high)} Hz is where
          ISO 226 has data; the shaded band above it is held flat.
        </LegendNote>
      </Legend>
    </PlotCard>
  );
}

interface ReadoutValues {
  hz: number;
  x: number;
  target: number;
  response: number | null;
}

function readoutAt(data: LevelData, index: number, shift: number): ReadoutValues | null {
  if (data.kind === 'unknown') {
    return null;
  }
  const hz = meta.gridHz[index];
  const target = data.target[index];
  if (hz === undefined || target === undefined) {
    return null;
  }
  const response = data.kind === 'served' ? data.response[index] : undefined;
  return {
    hz,
    x: xOf(hz),
    // Shifted, so the numbers read off the tooltip are the numbers the axis
    // shows. The residual figure is not: the preamp cancels out of a difference.
    target: target + shift,
    response: response === undefined ? null : response + shift,
  };
}

function describe(data: LevelData, hearing: Hearing): string {
  const sign = data.offset >= 0 ? '+' : '';
  // The bypass state is announced too: a screen reader user toggling it has
  // even less to go on than a sighted one, who at least sees the trace fade.
  const audible =
    hearing === null
      ? ''
      : hearing === 'flat'
        ? ' The preview is bypassed, so the flat reference is what is playing.'
        : ' The preview is playing this compensated response.';
  if (data.kind !== 'served') {
    return (
      `Compensation target for a ${sign}${data.offset} dB offset. ` +
      `No filter set is served at this level.${audible}`
    );
  }
  return (
    `Compensation for a ${sign}${data.offset} dB offset: ${data.filters.length} bands ` +
    `matching the ISO target to within ${data.maxResidualDb} dB between ` +
    `${publishedHz(isoBandHz.low)} and ${publishedHz(isoBandHz.high)} Hz.${audible}`
  );
}
