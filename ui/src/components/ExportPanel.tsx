import { useState } from 'react';
import { Check, Copy, Download } from 'lucide-react';

import type { ExportContext, ExportFormat } from '../export/formats';
import { FORMAT_LABELS, filename, render } from '../export/formats';

const ORDER: ExportFormat[] = ['camilladsp', 'apo', 'roon', 'csv', 'json'];

export function ExportPanel({ context }: { context: ExportContext }) {
  const [format, setFormat] = useState<ExportFormat>('camilladsp');
  const [copied, setCopied] = useState(false);

  // Rendering five short strings costs less than deciding whether to.
  const text = render(format, context);
  const name = filename(format, context);

  const copy = async () => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  };

  const download = () => {
    const url = URL.createObjectURL(new Blob([text], { type: 'text/plain' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = name;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <section className="rounded-3xl border border-slate-800 bg-panel p-6 shadow-xl">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 text-sm font-semibold tracking-widest text-slate-400 uppercase">
          <Download className="h-4 w-4 text-accent" />
          Export
        </h2>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={copy}
            className="flex items-center gap-1.5 rounded-xl border border-slate-700 bg-ink px-3 py-2 text-sm text-slate-300 hover:border-slate-600 hover:text-white"
          >
            {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
            {copied ? 'Copied' : 'Copy'}
          </button>
          <button
            type="button"
            onClick={download}
            className="flex items-center gap-1.5 rounded-xl border border-accent/40 bg-accent/20 px-3 py-2 text-sm font-semibold text-indigo-100 hover:bg-accent/30"
          >
            <Download className="h-3.5 w-3.5" />
            {name}
          </button>
        </div>
      </div>

      <div className="mb-3 flex flex-wrap gap-2" role="tablist" aria-label="Export format">
        {ORDER.map((option) => (
          <button
            key={option}
            type="button"
            role="tab"
            aria-selected={format === option}
            onClick={() => setFormat(option)}
            className={`rounded-xl border px-3 py-1.5 text-sm transition-colors ${
              format === option
                ? 'border-accent/40 bg-accent/20 text-indigo-200'
                : 'border-slate-800 bg-ink text-slate-400 hover:border-slate-700 hover:text-slate-200'
            }`}
          >
            {FORMAT_LABELS[option].name}
          </button>
        ))}
      </div>

      <p className="mb-3 text-sm text-slate-400">{FORMAT_LABELS[format].note}</p>

      <pre className="max-h-72 overflow-auto rounded-2xl border border-slate-800 bg-ink p-4 font-mono text-sm leading-relaxed text-slate-300">
        {text}
      </pre>
    </section>
  );
}
