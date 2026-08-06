import { useState } from 'react';
import { Check, Share2 } from 'lucide-react';

/**
 * Share the current level as a link.
 *
 * `navigator.share` exists on Android, iOS and Safari and opens the platform
 * sheet; desktop Firefox and Chrome do not implement it, so the fallback —
 * copying to the clipboard — is the common path rather than an edge case, and
 * gets the visible confirmation.
 *
 * The URL is built from state at click time rather than read from the address
 * bar, which the page rewrites on a short delay and could still be a level
 * behind.
 */
type Outcome = 'idle' | 'copied' | 'failed';

interface Props {
  url: string;
  /** What the link points at, for the platform share sheet. */
  title: string;
}

export function ShareButton({ url, title }: Props) {
  const [outcome, setOutcome] = useState<Outcome>('idle');

  const announce = (result: Outcome) => {
    setOutcome(result);
    window.setTimeout(() => setOutcome('idle'), 1800);
  };

  const share = async () => {
    if (navigator.share) {
      try {
        await navigator.share({ title, url });
        return;
      } catch (error) {
        // Dismissing the sheet is a decision, not a failure to report.
        if (error instanceof Error && error.name === 'AbortError') {
          return;
        }
      }
    }
    try {
      await navigator.clipboard.writeText(url);
      announce('copied');
    } catch {
      announce('failed');
    }
  };

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => void share()}
        aria-label="Share a link to this listening level"
        title="Share a link to this listening level"
        className="flex items-center rounded-2xl border border-slate-800 bg-panel px-3.5 py-2 text-slate-300 transition-colors hover:bg-slate-800/60 hover:text-white"
      >
        {outcome === 'copied' ? (
          <Check className="h-4 w-4 text-emerald-400" />
        ) : (
          <Share2 className="h-4 w-4" />
        )}
      </button>
      <span
        role="status"
        aria-live="polite"
        className={`pointer-events-none absolute top-full right-0 mt-1.5 rounded-lg border border-slate-700 bg-ink px-2 py-1 text-[11px] whitespace-nowrap text-slate-300 transition-opacity ${
          outcome === 'idle' ? 'opacity-0' : 'opacity-100'
        }`}
      >
        {outcome === 'failed' ? 'Copy the address bar' : outcome === 'copied' ? 'Link copied' : ''}
      </span>
    </div>
  );
}
