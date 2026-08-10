/**
 * Chrome shared by the two figures.
 *
 * The response and the residual are separate `<svg>`s in separate cards, each
 * with its own vertical scale, its own frequency axis and its own legend. This
 * module is what keeps them looking like two views of one thing rather than two
 * unrelated charts: same card, same axis, same legend grammar.
 */
import type { ReactNode } from 'react';

import { FREQUENCY_TICKS, WIDTH, frames, xOf } from '../plot/geometry';

/**
 * What the preview is putting through the speakers, or null when it is not
 * running. One tri-state rather than a `playing`/`bypassed` pair, which can
 * express a combination that does not exist (bypassed while stopped) and would
 * leave the plot deciding what that meant.
 */
export type Hearing = 'compensated' | 'flat' | null;

export function PlotCard({
  icon,
  title,
  aside,
  children,
}: {
  icon: ReactNode;
  title: string;
  aside: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="rounded-3xl border border-slate-800 bg-panel p-4 shadow-xl sm:p-6">
      {/* Nothing in this row may depend on the preview state. Everything above
          a figure is layout that figure's position rests on, and a chip that
          appeared here when the preview started grew the row by 10px on a wide
          window and by a wrapped line on a narrow one -- so starting the
          preview moved the plot out from under the pointer. State is announced
          in the legend instead, where the row can grow freely. */}
      <header className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-sm font-semibold tracking-widest text-slate-400 uppercase">
          <span className="text-accent">{icon}</span>
          {title}
        </h2>
        <p className="font-mono text-sm text-slate-400">{aside}</p>
      </header>
      {children}
    </section>
  );
}

/** The inset the `<svg>` sits in. Identical in both cards, so they register. */
export function PlotFrame({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-ink p-1 sm:p-2">{children}</div>
  );
}

/**
 * Vertical gridlines and the frequency labels beneath them.
 *
 * Both figures draw their own. One shared axis under the lower panel was the
 * arrangement that prompted this split: reading a feature off the upper figure
 * meant dropping past a second panel to find out what frequency it was at.
 */
export function FrequencyGrid({ top, bottom }: { top: number; bottom: number }) {
  return (
    <g>
      {FREQUENCY_TICKS.map(({ hz, label }) => (
        <g key={hz}>
          <line
            x1={xOf(hz)}
            y1={top}
            x2={xOf(hz)}
            y2={bottom}
            className="stroke-slate-700/40"
            strokeWidth={1}
          />
          {label && (
            <text
              x={xOf(hz)}
              y={bottom + 18}
              textAnchor="middle"
              className="fill-slate-500 text-[11px]"
            >
              {label}
            </text>
          )}
        </g>
      ))}
      <text
        x={frames.right}
        y={bottom + 18}
        textAnchor="end"
        className="fill-slate-600 text-[10px]"
      >
        Hz
      </text>
    </g>
  );
}

export function Legend({ children }: { children: ReactNode }) {
  return (
    <dl className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-1.5 text-sm text-slate-400">
      {children}
    </dl>
  );
}

export function Key({ className, label }: { className: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className={`inline-block h-0.5 w-5 rounded-full ${className}`} />
      {label}
    </span>
  );
}

/** A note closing a legend, in the same row so it wraps with the keys. */
export function LegendNote({ children }: { children: ReactNode }) {
  return <span className="text-slate-400">{children}</span>;
}

/**
 * The tooltip body, placed on whichever side of the crosshair has room.
 *
 * `width`/`height` are viewBox units rather than measured, because SVG has no
 * layout: the caller knows how many lines it is about to draw.
 */
export function Readout({
  x,
  top,
  width,
  height,
  children,
}: {
  x: number;
  top: number;
  width: number;
  height: number;
  children: ReactNode;
}) {
  const flip = x > WIDTH / 2;
  return (
    <g transform={`translate(${flip ? x - width - 12 : x + 12}, ${top})`}>
      <rect width={width} height={height} rx={10} className="fill-ink/95 stroke-slate-700" />
      {children}
    </g>
  );
}
