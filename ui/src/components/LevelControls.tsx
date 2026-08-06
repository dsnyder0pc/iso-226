import { Disc3, RotateCcw, Volume2 } from 'lucide-react';

import { REFERENCE_RANGE, meta } from '../data';
import { formatOffset } from '../format';

/**
 * References the offset equivalence is documented across. Outside this window
 * the "one ladder covers every reference" claim has not been measured, so the
 * UI says so rather than quietly extrapolating it.
 */
const MEASURED_REFERENCE = { min: 72, max: 85 };

interface Props {
  level: number;
  reference: number;
  offset: number;
  onLevel: (level: number) => void;
  onReference: (reference: number) => void;
  onReset: () => void;
}

export function LevelControls({
  level,
  reference,
  offset,
  onLevel,
  onReference,
  onReset,
}: Props) {
  const min = reference + meta.servable.min;
  const max = reference + meta.servable.max;
  const quick = [0, -5, -10, -15, -20, meta.servable.min];
  const referenceIsMeasured =
    reference >= MEASURED_REFERENCE.min && reference <= MEASURED_REFERENCE.max;

  return (
    <section className="rounded-3xl border border-slate-800 bg-panel p-6 shadow-xl">
      <div className="mb-5 flex items-center justify-between border-b border-slate-800/80 pb-3">
        <h2 className="flex items-center gap-2 text-xs font-semibold tracking-widest text-slate-400 uppercase">
          <Volume2 className="h-4 w-4 text-accent" />
          Listening parameters
        </h2>
        <button
          type="button"
          onClick={onReset}
          className="flex items-center gap-1 rounded-lg px-2 py-1 text-xs text-slate-500 hover:bg-slate-800/50 hover:text-slate-300"
        >
          <RotateCcw className="h-3 w-3" />
          Reset
        </button>
      </div>

      <div className="grid grid-cols-1 items-start gap-6 md:grid-cols-12">
        <div className="space-y-3 md:col-span-8">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <label
              htmlFor="level"
              className="text-sm font-semibold text-white"
            >
              Listening level
              <span className="ml-2 font-normal text-slate-500">
                measured broadband, C-weighted, slow
              </span>
            </label>
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs text-slate-400">
                offset <strong className="text-accent">{formatOffset(offset)}</strong>
              </span>
              <input
                id="level"
                type="number"
                min={min}
                max={max}
                step={1}
                value={level}
                onChange={(event) => onLevel(Number(event.target.value))}
                className="w-20 rounded-xl border border-slate-700 bg-ink px-2.5 py-1 text-right font-mono text-sm font-semibold text-white focus:border-accent focus:outline-none"
              />
              <span className="text-xs text-slate-400">dB SPL</span>
            </div>
          </div>

          <input
            type="range"
            aria-label="Listening level"
            min={min}
            max={max}
            step={1}
            value={Math.min(max, Math.max(min, level))}
            onChange={(event) => onLevel(Number(event.target.value))}
            className="w-full cursor-pointer"
          />
          <div className="flex justify-between px-0.5 font-mono text-[10px] text-slate-500">
            <span>{min} dB</span>
            <span>{reference} dB reference</span>
            <span>{max} dB</span>
          </div>

          <div className="flex flex-wrap items-center gap-2 pt-1">
            {quick.map((step) => (
              <button
                key={step}
                type="button"
                onClick={() => onLevel(reference + step)}
                className={`rounded-xl border px-3 py-1 font-mono text-xs transition-colors ${
                  offset === step
                    ? 'border-accent/40 bg-accent/20 text-indigo-200'
                    : 'border-slate-800 bg-ink text-slate-400 hover:border-slate-700 hover:text-slate-200'
                }`}
              >
                {step === 0 ? 'reference' : formatOffset(step)}
              </button>
            ))}
          </div>
        </div>

        <div className="space-y-2 rounded-2xl border border-slate-700/50 bg-inset p-4 md:col-span-4">
          <label
            htmlFor="reference"
            className="flex items-center gap-1.5 text-xs font-semibold text-slate-300"
          >
            <Disc3 className="h-3.5 w-3.5 text-accent" />
            Mastering reference
          </label>
          <div className="flex items-center gap-2">
            <input
              id="reference"
              type="number"
              min={REFERENCE_RANGE[0]}
              max={REFERENCE_RANGE[1]}
              step={1}
              value={reference}
              onChange={(event) => onReference(Number(event.target.value))}
              className="w-full rounded-xl border border-slate-700 bg-ink px-3 py-1.5 font-mono text-sm font-semibold text-white focus:border-accent focus:outline-none"
            />
            <span className="font-mono text-xs text-slate-400">dB</span>
          </div>
          <p className="text-[11px] leading-tight text-slate-500">
            A property of the recording, not of the room. The nominal value is{' '}
            {meta.nominalReferenceDb} dB.
          </p>
          {!referenceIsMeasured && (
            <p className="text-[11px] leading-tight text-amber-300/90">
              Outside {MEASURED_REFERENCE.min}–{MEASURED_REFERENCE.max} dB the
              equivalence between references has not been measured. These filters
              are still the ones for a {formatOffset(offset)} offset, but the{' '}
              {meta.equivalenceToleranceDb} dB bound does not apply.
            </p>
          )}
        </div>
      </div>
    </section>
  );
}
