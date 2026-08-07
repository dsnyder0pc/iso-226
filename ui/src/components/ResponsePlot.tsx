import { useMemo, useState } from 'react';
import { Activity } from 'lucide-react';

import { isoBandHz, meta } from '../data';
import type { LevelData } from '../data/types';
import {
  FREQUENCY_TICKS,
  HEIGHT,
  RESIDUAL_BOUND,
  WIDTH,
  gainTicks,
  hzAt,
  nearestIndex,
  panels,
  pathsFor,
  residualTicks,
  xOf,
  yOfGain,
  yOfResidual,
} from '../plot/geometry';
import { publishedHz } from '../format';

/**
 * What the preview is putting through the speakers, or null when it is not
 * running. One tri-state rather than a `playing`/`bypassed` pair, which can
 * express a combination that does not exist (bypassed while stopped) and would
 * leave this component deciding what that meant.
 */
export type Hearing = 'compensated' | 'flat' | null;

interface Props {
  data: LevelData;
  hearing: Hearing;
}

const HELD_HIGH_X = xOf(isoBandHz.high);

export function ResponsePlot({ data, hearing }: Props) {
  const [hover, setHover] = useState<number | null>(null);
  const paths = useMemo(() => pathsFor(data.offset), [data.offset]);

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
    <section className="rounded-3xl border border-slate-800 bg-panel p-4 shadow-xl sm:p-6">
      {/* Nothing in this row may depend on `hearing`. Everything above the
          figure is layout the plot's position rests on, and a chip that
          appeared here when the preview started grew the row by 10px on a wide
          window and by a wrapped line on a narrow one -- so starting the
          preview moved the plot out from under the pointer. The state is
          announced under the figure instead, where the row can grow freely. */}
      <header className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-sm font-semibold tracking-widest text-slate-400 uppercase">
          <Activity className="h-4 w-4 text-accent" />
          Frequency response
        </h2>
        <p className="font-mono text-sm text-slate-400">
          {data.kind === 'served'
            ? `preamp ${data.headroomDb.toFixed(1)} dB applied`
            : `preamp ${paths.shift.toFixed(1)} dB required`}{' '}
          · evaluated at {(meta.designFs / 1000).toFixed(1)} kHz
        </p>
      </header>

      <div className="rounded-2xl border border-slate-800 bg-ink p-1 sm:p-2">
        <svg
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          // pan-y, not none: the plot is a tall slab of a touch screen, and
          // touch-action: none there means a finger swiped over it cannot
          // scroll the page. Vertical drags stay with the browser; horizontal
          // ones still reach the crosshair.
          className="w-full touch-pan-y"
          role="img"
          aria-label={describe(data, hearing)}
          onPointerMove={(event) => {
            const box = event.currentTarget.getBoundingClientRect();
            const x = ((event.clientX - box.left) / box.width) * WIDTH;
            setHover(nearestIndex(hzAt(x)));
          }}
          onPointerLeave={() => setHover(null)}
          // A touch readout survives lifting the finger -- that is how you
          // read a value on a tablet -- but not the browser stealing the
          // gesture to scroll, which would strand the crosshair mid-page.
          onPointerCancel={() => setHover(null)}
        >
          <defs>
            <clipPath id="residual-strip">
              <rect
                x={panels.left}
                y={panels.residual.top}
                width={panels.right - panels.left}
                height={panels.residual.height}
              />
            </clipPath>
          </defs>

          {/* Above 12.5 kHz ISO has no data and the target is held flat; the
              filters are constrained there, never optimized there. The view
              starts at 20 Hz, so the matching region at the bottom is off the
              left edge rather than shaded. */}
          <rect
            x={HELD_HIGH_X}
            y={panels.main.top}
            width={panels.right - HELD_HIGH_X}
            height={panels.residual.bottom - panels.main.top}
            className="fill-slate-100/[0.035]"
          />

          {FREQUENCY_TICKS.map(({ hz, label }) => (
            <g key={hz}>
              <line
                x1={xOf(hz)}
                y1={panels.main.top}
                x2={xOf(hz)}
                y2={panels.main.bottom}
                className="stroke-slate-700/40"
                strokeWidth={1}
              />
              <line
                x1={xOf(hz)}
                y1={panels.residual.top}
                x2={xOf(hz)}
                y2={panels.residual.bottom}
                className="stroke-slate-700/40"
                strokeWidth={1}
              />
              {label && (
                <text
                  x={xOf(hz)}
                  y={panels.residual.bottom + 18}
                  textAnchor="middle"
                  className="fill-slate-500 text-[11px]"
                >
                  {label}
                </text>
              )}
            </g>
          ))}

          {gainTicks().map((db) => (
            <g key={db}>
              <line
                x1={panels.left}
                y1={yOfGain(db)}
                x2={panels.right}
                y2={yOfGain(db)}
                className="stroke-slate-700/40"
                strokeWidth={1}
              />
              <text
                x={panels.left - 8}
                y={yOfGain(db) + 4}
                textAnchor="end"
                className="fill-slate-500 text-[11px]"
              >
                {db > 0 ? `+${db}` : db}
              </text>
            </g>
          ))}

          {/* 0 dBFS. With the preamp applied the response sits below this, which
              is the whole point of publishing a headroom figure. */}
          <line
            x1={panels.left}
            y1={yOfGain(0)}
            x2={panels.right}
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
            x1={panels.left}
            y1={yOfGain(paths.shift)}
            x2={panels.right}
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
            />
          ))}

          <path
            d={paths.target}
            fill="none"
            className="stroke-target"
            strokeWidth={5}
            strokeLinejoin="round"
            opacity={0.55}
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

          {/* Residual strip. Its bound is the published figure, so the trace
              cannot contradict the number printed beside it. */}
          {residualTicks().map((db) => (
            <g key={db}>
              <line
                x1={panels.left}
                y1={yOfResidual(db)}
                x2={panels.right}
                y2={yOfResidual(db)}
                className={db === 0 ? 'stroke-slate-500/70' : 'stroke-slate-700/40'}
                strokeWidth={1}
              />
              <text
                x={panels.left - 8}
                y={yOfResidual(db) + 4}
                textAnchor="end"
                className="fill-slate-500 text-[10px]"
              >
                {db === 0 ? '0' : `${db > 0 ? '+' : ''}${db.toFixed(2)}`}
              </text>
            </g>
          ))}
          {served && (
            <>
              {/* Signed separately: at the pass-through preset both bounds are
                  zero, and 0 and -0 are the same React key. */}
              {[1, -1].map((sign) => (
                <line
                  key={sign}
                  x1={panels.left}
                  y1={yOfResidual(sign * served.maxResidualDb)}
                  x2={panels.right}
                  y2={yOfResidual(sign * served.maxResidualDb)}
                  className="stroke-amber-400/45"
                  strokeWidth={1}
                  strokeDasharray="4 4"
                />
              ))}
              {paths.residual && (
                <path
                  d={paths.residual}
                  fill="none"
                  className="stroke-emerald-400"
                  strokeWidth={1.5}
                  // The strip is scaled to the in-band residual; the held
                  // regions run well past it and are clipped rather than
                  // allowed to paint over the response above.
                  clipPath="url(#residual-strip)"
                />
              )}
            </>
          )}

          <text
            x={panels.left - 8}
            y={panels.residual.top - 8}
            textAnchor="end"
            className="fill-slate-500 text-[10px]"
          >
            dB
          </text>
          <text
            x={panels.left + 2}
            y={panels.residual.top - 8}
            className="fill-slate-400 text-[11px]"
          >
            Residual — published set against the ISO target
          </text>
          <text
            x={HELD_HIGH_X + 14}
            y={panels.main.top + 14}
            className="fill-slate-500 text-[10px]"
            textAnchor="end"
            transform={`rotate(-90 ${HELD_HIGH_X + 14} ${panels.main.top + 14})`}
          >
            held flat
          </text>

          {readout && (
            <g pointerEvents="none">
              <line
                x1={readout.x}
                y1={panels.main.top}
                x2={readout.x}
                y2={panels.residual.bottom}
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
              <g
                transform={`translate(${
                  readout.x > WIDTH / 2 ? readout.x - 196 : readout.x + 12
                }, ${panels.main.top + 10})`}
              >
                <rect
                  width={184}
                  height={readout.response === null ? 46 : 82}
                  rx={10}
                  className="fill-ink/95 stroke-slate-700"
                />
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
                {readout.residual !== null && (
                  <text x={12} y={74} className="fill-emerald-400 font-mono text-[11px]">
                    residual {readout.residual >= 0 ? '+' : ''}
                    {readout.residual.toFixed(4)} dB
                  </text>
                )}
              </g>
            </g>
          )}
        </svg>
      </div>

      <Legend served={served !== null} hearing={hearing} />
    </section>
  );
}

function Legend({ served, hearing }: { served: boolean; hearing: Hearing }) {
  const flatIsLive = hearing === 'flat';
  return (
    <dl className="mt-3 flex flex-wrap gap-x-5 gap-y-1.5 text-sm text-slate-400">
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
              ? 'border-amber-500/40 bg-amber-500/15 text-amber-100'
              : 'border-accent/40 bg-accent/15 text-accent'
          }`}
        >
          <span
            className={`inline-block h-0.5 w-5 rounded-full ${
              flatIsLive ? 'bg-slate-300' : 'bg-accent'
            }`}
          />
          Hearing {flatIsLive ? 'flat — filters off' : 'the compensated response'}
        </span>
      )}
      <Key className="bg-target/60" label={`ISO ${meta.isoEdition.slice(4)} target`} />
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
        label={
          flatIsLive ? 'Flat reference (playing now)' : 'Flat reference (the preamp)'
        }
      />
      {served && <Key className="bg-emerald-400" label="Residual" />}
      {served && <Key className="bg-amber-400/60" label="± the published max residual" />}
      <span className="text-slate-400">
        {publishedHz(isoBandHz.low)}–{publishedHz(isoBandHz.high)} Hz is where ISO 226 has data;
        the shaded band above it is held flat. Residual strip spans ±{RESIDUAL_BOUND} dB across the
        whole ladder and is clipped outside the ISO range.
      </span>
    </dl>
  );
}

function Key({ className, label }: { className: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className={`inline-block h-0.5 w-5 rounded-full ${className}`} />
      {label}
    </span>
  );
}

interface Readout {
  hz: number;
  x: number;
  target: number;
  response: number | null;
  residual: number | null;
}

function readoutAt(data: LevelData, index: number, shift: number): Readout | null {
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
    // shows. The residual is not: the preamp cancels out of a difference.
    target: target + shift,
    response: response === undefined ? null : response + shift,
    residual: data.kind === 'served' ? (data.residual[index] ?? null) : null,
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
