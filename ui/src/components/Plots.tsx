import { useState } from 'react';

import type { LevelData } from '../data/types';
import type { Hearing } from './PlotParts';
import { ResponsePlot } from './ResponsePlot';
import { ResidualPlot } from './ResidualPlot';

interface Props {
  data: LevelData;
  hearing: Hearing;
}

/**
 * The two figures and the one thing they share: the crosshair.
 *
 * Splitting the response and the residual into separate cards is what a
 * reviewer asked for — one legend over two vertical scales read as one
 * confusing graph — but reading a bump on the response against the error at
 * the same frequency is why they were stacked in the first place. Hovering
 * either figure therefore marks both.
 *
 * The state lives here rather than in `App` so that a pointer moving across a
 * plot re-renders two figures and not the metrics, the filter table and the
 * export panel underneath them.
 */
export function Plots({ data, hearing }: Props) {
  const [hover, setHover] = useState<number | null>(null);
  return (
    <>
      <ResponsePlot data={data} hearing={hearing} hover={hover} onHover={setHover} />
      {data.kind === 'served' && data.filters.length > 0 && (
        <ResidualPlot data={data} hover={hover} onHover={setHover} />
      )}
    </>
  );
}
