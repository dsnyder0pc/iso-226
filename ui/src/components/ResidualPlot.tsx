import { Ruler } from 'lucide-react';

import { isoBandHz, meta } from '../data';
import type { ServedLevel } from '../data/types';
import {
  RESIDUAL_BOUND,
  WIDTH,
  frames,
  hzAt,
  nearestIndex,
  pathsFor,
  residualTicks,
  xOf,
  yOfResidual,
} from '../plot/geometry';
import { publishedHz } from '../format';
import {
  FrequencyGrid,
  Key,
  Legend,
  LegendNote,
  PlotCard,
  PlotFrame,
  Readout,
} from './PlotParts';

interface Props {
  data: ServedLevel;
  hover: number | null;
  onHover: (index: number | null) => void;
}

const HELD_HIGH_X = xOf(isoBandHz.high);

/**
 * How far the published cascade misses the ISO target, as its own figure.
 *
 * Separate from the response, and drawn *without* the preamp: the residual is
 * `response - target`, and a constant shift applied to both cancels out of a
 * difference. That is the reason these two cannot share a vertical scale, and
 * ultimately the reason they are no longer one figure.
 */
export function ResidualPlot({ data, hover, onHover }: Props) {
  const paths = pathsFor(data.offset);
  if (!paths?.residual) {
    return null;
  }
  const hz = hover === null ? undefined : meta.gridHz[hover];
  const value = hover === null ? undefined : data.residual[hover];
  const readout =
    hz === undefined || value === undefined ? null : { hz, value, x: xOf(hz) };

  return (
    <PlotCard
      icon={<Ruler className="h-4 w-4" />}
      title="Residual"
      aside={<>worst {data.maxResidualDb.toFixed(4)} dB in band · preamp excluded</>}
    >
      <PlotFrame>
        <svg
          viewBox={`0 0 ${WIDTH} ${frames.residual.viewHeight}`}
          className="w-full touch-pan-y"
          role="img"
          aria-label={
            `Error of the published five-band set against the ISO target for a ` +
            `${data.offset >= 0 ? '+' : ''}${data.offset} dB offset: within ` +
            `${data.maxResidualDb} dB between ${publishedHz(isoBandHz.low)} and ` +
            `${publishedHz(isoBandHz.high)} Hz.`
          }
          onPointerMove={(event) => {
            const box = event.currentTarget.getBoundingClientRect();
            onHover(nearestIndex(hzAt(((event.clientX - box.left) / box.width) * WIDTH)));
          }}
          onPointerLeave={() => onHover(null)}
          onPointerCancel={() => onHover(null)}
        >
          <defs>
            <clipPath id="residual-strip">
              <rect
                x={frames.left}
                y={frames.residual.top}
                width={frames.right - frames.left}
                height={frames.residual.height}
              />
            </clipPath>
          </defs>

          <rect
            x={HELD_HIGH_X}
            y={frames.residual.top}
            width={frames.right - HELD_HIGH_X}
            height={frames.residual.height}
            className="fill-slate-100/[0.035]"
          />

          <FrequencyGrid top={frames.residual.top} bottom={frames.residual.bottom} />

          {residualTicks().map((db) => (
            <g key={db}>
              <line
                x1={frames.left}
                y1={yOfResidual(db)}
                x2={frames.right}
                y2={yOfResidual(db)}
                className={db === 0 ? 'stroke-slate-500/70' : 'stroke-slate-700/40'}
                strokeWidth={1}
              />
              <text
                x={frames.left - 8}
                y={yOfResidual(db) + 4}
                textAnchor="end"
                className="fill-slate-500 text-[11px]"
              >
                {db === 0 ? '0' : `${db > 0 ? '+' : ''}${db.toFixed(2)}`}
              </text>
            </g>
          ))}
          <text
            x={frames.left - 8}
            y={frames.residual.top - 4}
            textAnchor="end"
            className="fill-slate-500 text-[10px]"
          >
            dB
          </text>

          {/* Signed separately: at the pass-through preset both bounds are
              zero, and 0 and -0 are the same React key. */}
          {[1, -1].map((sign) => (
            <line
              key={sign}
              x1={frames.left}
              y1={yOfResidual(sign * data.maxResidualDb)}
              x2={frames.right}
              y2={yOfResidual(sign * data.maxResidualDb)}
              className="stroke-slate-400/50"
              strokeWidth={1}
              strokeDasharray="4 4"
            />
          ))}

          <path
            d={paths.residual}
            fill="none"
            className="stroke-emerald-400"
            strokeWidth={1.5}
            // The strip is scaled to the in-band residual; the held regions run
            // well past it and are clipped rather than allowed to paint over
            // the axis below.
            clipPath="url(#residual-strip)"
          />

          {readout && (
            <g pointerEvents="none">
              <line
                x1={readout.x}
                y1={frames.residual.top}
                x2={readout.x}
                y2={frames.residual.bottom}
                className="stroke-slate-300/40"
                strokeWidth={1}
              />
              {/* No dot when the value is off-scale: out in the held regions
                  the residual runs well past the strip, and a marker pinned to
                  the edge would report a number that is not the one there. The
                  text still gives it. */}
              {Math.abs(readout.value) <= RESIDUAL_BOUND && (
                <circle
                  cx={readout.x}
                  cy={yOfResidual(readout.value)}
                  r={3}
                  className="fill-emerald-400"
                />
              )}
              {/* One line, not the response figure's stacked card: this panel
                  is 110 units tall and a card that size would cover the trace
                  it is annotating. */}
              <Readout x={readout.x} top={frames.residual.top + 4} width={168} height={26}>
                <text x={11} y={18} className="fill-slate-100 font-mono text-[11px]">
                  {publishedHz(readout.hz)} Hz ·{' '}
                  <tspan className="fill-emerald-400">
                    {readout.value >= 0 ? '+' : ''}
                    {readout.value.toFixed(4)} dB
                  </tspan>
                </text>
              </Readout>
            </g>
          )}
        </svg>
      </PlotFrame>

      <Legend>
        <Key className="bg-emerald-400" label="Published set minus the ISO target" />
        <Key className="bg-slate-400/50" label="± the published max residual" />
        <LegendNote>
          Scale is fixed at ±{RESIDUAL_BOUND} dB across the whole ladder, so the quiet
          end visibly fits worse. Clipped outside {publishedHz(isoBandHz.low)}–
          {publishedHz(isoBandHz.high)} Hz, where the fit is constrained rather than
          optimized.
        </LegendNote>
      </Legend>

      <p className="mt-4 rounded-2xl border border-slate-800/80 bg-ink p-4 text-base leading-relaxed text-slate-400">
        This is the error you are actually getting. It is measured on the{' '}
        <strong className="text-slate-200">published, rounded</strong> values in the
        filter table below — not on an unrounded fit behind them — and on the filter
        cascade alone, before the headroom adjustment, because a constant preamp
        cancels out of the difference between two curves.
      </p>
    </PlotCard>
  );
}
