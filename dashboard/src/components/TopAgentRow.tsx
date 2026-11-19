import { useEffect, useRef, useState } from 'react';
import type { AgentLeaderboardEntry } from '../types';
import { formatPct } from '../utils/formatters';
import { cn } from '../utils/cn';
import { CategoryBadge } from './ui/CategoryBadge';
import { useFlashOnChange } from '../hooks/useFlashOnChange';
import { useIntroDone } from '../hooks/useIntro';
import { getAgentName } from '../lib/agentNames';

interface TopAgentRowProps {
  agent: AgentLeaderboardEntry;
  rank: number;
  delayMs: number;
  /** Whether the Top 3 strip should step up at all this page load -- false on a refresh (or
   * any later mount) once it has already played this browser session, so the row renders in
   * its final place immediately instead of replaying. */
  play: boolean;
}

/** One row of the Home page "Live Standings · Top 3 Agents Today" strip: steps up into place
 * once per page visit (never replays when the data refreshes or the page is reloaded), shows
 * its return % exactly as given (no count-up), then flashes briefly on later value changes.
 * The #1 row additionally fades in a static boxed glow once it lands -- see .top-row-step* in
 * index.css. */
export default function TopAgentRow({ agent, rank, delayMs, play }: TopAgentRowProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(!play);
  const introDone = useIntroDone();

  useEffect(() => {
    if (!play) return;
    // Wait for the brand intro overlay to finish (or be skipped) before stepping up, so it
    // never plays underneath/behind it -- same step-up animation, just delayed to start.
    if (!introDone) return;
    const id = requestAnimationFrame(() => setVisible(true));
    return () => cancelAnimationFrame(id);
  }, [introDone, play]);

  const flashClass = useFlashOnChange(agent.returnPct);

  const isFirst = rank === 0;
  const isPositive = agent.returnPct >= 0;
  const cleanName = getAgentName(agent.id, agent.name);

  return (
    <div
      ref={ref}
      className={cn(
        'flex items-center justify-between transition-colors',
        play && 'top-row-step',
        play && visible && 'top-row-step--play',
        isFirst ? 'top-row-step--first text-white' : 'py-2 text-zinc-300',
        isFirst && visible && 'top-row-step--first-glow'
      )}
      style={{ animationDelay: play && visible ? `${delayMs}ms` : undefined }}
    >
      <div className="flex items-center gap-2.5 min-w-0">
        <span className={cn('font-mono text-xs', isFirst ? 'top-row-step--first-rank font-bold' : 'text-zinc-600')}>
          #{rank + 1}
        </span>
        <span className={cn('truncate font-sans', isFirst ? 'top-row-step--first-name font-semibold text-white' : 'text-xs text-zinc-300')}>
          {cleanName}
        </span>
        <CategoryBadge type={agent.id} />
      </div>

      <div
        className={cn(
          'font-mono font-bold tabular-nums text-right flex-shrink-0 px-1 transition-colors duration-[600ms]',
          isFirst ? 'text-sm font-extrabold' : 'text-xs',
          isPositive ? 'text-positive' : 'text-negative',
          flashClass
        )}
      >
        {formatPct(agent.returnPct)}
      </div>
    </div>
  );
}
