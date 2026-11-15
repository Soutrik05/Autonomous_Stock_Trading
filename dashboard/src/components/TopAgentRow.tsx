import { useEffect, useRef, useState } from 'react';
import type { AgentLeaderboardEntry } from '../types';
import { formatPct } from '../utils/formatters';
import { cn } from '../utils/cn';
import { CategoryBadge } from './ui/CategoryBadge';
import { useCountUp } from '../hooks/useCountUp';
import { useFlashOnChange } from '../hooks/useFlashOnChange';

interface TopAgentRowProps {
  agent: AgentLeaderboardEntry;
  rank: number;
  staggerMs: number;
}

/** One row of the Home page "Live Standings · Top 3 Agents Today" strip: slides in from the
 * left once, counts its return % up on first real appearance, then flashes on later changes. */
export default function TopAgentRow({ agent, rank, staggerMs }: TopAgentRowProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const id = requestAnimationFrame(() => setVisible(true));
    return () => cancelAnimationFrame(id);
  }, []);

  const countUpText = useCountUp(agent.returnPct, formatPct);
  const flashClass = useFlashOnChange(agent.returnPct);

  const isFirst = rank === 0;
  const isPositive = agent.returnPct >= 0;
  const cleanName = agent.name.replace(' (LLM)', '').replace('Baseline ', '');

  return (
    <div
      ref={ref}
      className={cn(
        'row-reveal flex items-center justify-between py-2 transition-colors',
        visible && 'row-reveal--visible',
        isFirst ? 'text-white' : 'text-zinc-300'
      )}
      style={{ transitionDelay: visible ? `${staggerMs}ms` : undefined }}
    >
      <div className="flex items-center gap-2.5 min-w-0">
        <span className={cn('font-mono text-xs', isFirst ? 'text-zinc-300 font-bold' : 'text-zinc-600')}>
          #{rank + 1}
        </span>
        <span className={cn('truncate font-sans', isFirst ? 'text-sm font-semibold text-white' : 'text-xs text-zinc-300')}>
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
        {countUpText}
      </div>
    </div>
  );
}
