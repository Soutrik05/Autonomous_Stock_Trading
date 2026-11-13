import { memo } from 'react';
import { Link } from 'react-router-dom';
import type { AgentLeaderboardEntry, NavHistoryPoint } from '../types';
import { formatPaiseToRupees, formatPct } from '../utils/formatters';
import { CategoryBadge } from './ui/CategoryBadge';
import { WarmupMetric } from './ui/WarmupMetric';
import { cn } from '../utils/cn';

interface BenchmarkMatrixTableProps {
  agents: AgentLeaderboardEntry[];
  navHistory?: NavHistoryPoint[];
  isCompact?: boolean;
}

function formatStrategyName(agent: AgentLeaderboardEntry): { name: string; isRules: boolean } {
  const isRules =
    agent.id.startsWith('baseline-') ||
    agent.id.includes('rules') ||
    agent.name.toLowerCase().includes('rules');

  let clean = agent.name
    .replace(/\s*\((LLM|Rules Control|Rules Baseline|Rules|Algorithmic Control Benchmark)\)/gi, '')
    .trim();

  clean = clean.replace(/^baseline[-:\s]*/i, '').trim();
  clean = clean.replace(/^rules[-:\s]*/i, '').trim();

  return { name: clean, isRules };
}

function getNavKeyForAgent(agentId: string): string {
  switch (agentId) {
    case 'simons': return 'simons';
    case 'baseline-simons-rules': return 'baselineSimons';
    case 'lynch': return 'lynch';
    case 'baseline-lynch-rules': return 'baselineLynch';
    case 'marks': return 'marks';
    case 'baseline-marks-rules': return 'baselineMarks';
    case 'jhunjhunwala': return 'jhunjhunwala';
    case 'baseline-rj-rules': return 'baselineRj';
    case 'stockminds-core':
    case 'varsity': return 'stockmindsCore';
    case 'baseline-varsity-rules': return 'baselineVarsity';
    default: return 'simons';
  }
}

function Sparkline({ data, isPositive }: { data: number[]; isPositive: boolean }) {
  if (!data || data.length < 2) return <span className="text-zinc-600 font-mono text-xs">—</span>;
  const width = 64;
  const height = 20;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const points = data.map((v, i) => {
    const x = (i / (data.length - 1)) * (width - 4) + 2;
    const y = height - 3 - ((v - min) / range) * (height - 6);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  const strokeColor = isPositive ? '#10B981' : '#C4553F';

  return (
    <svg width={width} height={height} className="overflow-visible inline-block">
      <path
        d={`M ${points.join(' L ')}`}
        fill="none"
        stroke={strokeColor}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function BenchmarkMatrixTableComponent({
  agents,
  navHistory,
  isCompact = false,
}: BenchmarkMatrixTableProps) {
  // Sort by return descending for clear leaderboard ranking
  const sorted = [...agents].sort((a, b) => b.returnPct - a.returnPct);
  const rows = isCompact ? sorted.slice(0, 5) : sorted;

  return (
    <div className="overflow-x-auto border border-border-hairline bg-[#161616] rounded-lg">
      <table className="w-full text-left border-collapse">
        {/* Table Header: whitespace-nowrap prevents two-row wrap */}
        <thead>
          <tr className="border-b border-border-hairline text-zinc-400 text-[11px] font-mono uppercase tracking-wider bg-[#121212] whitespace-nowrap">
            <th className="py-2.5 px-2 font-normal w-10 text-center text-zinc-500 whitespace-nowrap">Rank</th>
            <th className="py-2.5 px-3 font-normal min-w-[150px] text-left whitespace-nowrap">Agents</th>
            <th className="py-2.5 px-2 text-center font-normal min-w-[70px] whitespace-nowrap">Trajectory</th>
            <th className="py-2.5 px-3 text-center font-semibold min-w-[95px] text-white whitespace-nowrap">
              Net Return (%)
            </th>
            <th className="py-2.5 px-3 text-center font-normal min-w-[95px] text-zinc-400 whitespace-nowrap">
              Alpha vs Nifty (%)
            </th>
            <th className="py-2.5 px-3 text-center font-normal min-w-[95px] text-zinc-400 whitespace-nowrap">
              NAV (INR)
            </th>
            <th className="py-2.5 px-2 text-center font-normal min-w-[55px] text-zinc-400 whitespace-nowrap">
              Open Pos
            </th>
            <th className="py-2.5 px-2 text-center font-normal min-w-[55px] text-zinc-400 whitespace-nowrap">
              Trades
            </th>
            {!isCompact && (
              <>
                <th className="py-2.5 px-2.5 text-center font-normal min-w-[85px] text-zinc-400 whitespace-nowrap">Sharpe</th>
                <th className="py-2.5 px-2.5 text-center font-normal min-w-[85px] text-zinc-400 whitespace-nowrap">Max DD</th>
                <th className="py-2.5 px-2.5 text-center font-normal min-w-[85px] text-zinc-400 whitespace-nowrap">Win Rate</th>
              </>
            )}
          </tr>
        </thead>

        {/* Rows: Clear hierarchy with bold Return and muted supporting metrics */}
        <tbody className="divide-y divide-border-hairline text-sm font-sans whitespace-nowrap">
          {rows.map((ag, idx) => {
            const { name: displayName, isRules } = formatStrategyName(ag);
            const isRankOne = idx === 0;

            // Extract historical trajectory for inline sparkline
            const navKey = getNavKeyForAgent(ag.id);
            const series = navHistory
              ? navHistory.map((pt) => (pt as any)[navKey] as number).filter((v) => typeof v === 'number')
              : [];

            return (
              <tr
                key={ag.id}
                className={cn(
                  'transition-colors group hover:bg-white/[0.03]',
                  idx % 2 === 1 ? 'bg-white/[0.01]' : 'bg-transparent'
                )}
              >
                {/* Rank Numerals (Center) */}
                <td className="py-2.5 px-2 text-center">
                  <span
                    className={cn(
                      'font-mono text-xs tabular-nums',
                      isRankOne ? 'text-accent font-semibold' : 'text-zinc-500'
                    )}
                  >
                    {idx < 9 ? `0${idx + 1}` : idx + 1}
                  </span>
                </td>

                {/* Strategy Name (Left Aligned for Readability) */}
                <td className="py-2.5 px-3 text-left">
                  <div className="flex items-center gap-1.5">
                    <Link
                      to={`/portfolio/${ag.id}`}
                      className="font-sans font-medium text-sm text-zinc-100 hover:text-accent transition-colors truncate max-w-[170px]"
                    >
                      {displayName}
                    </Link>
                    <CategoryBadge type={isRules ? 'RULES' : 'LLM'} />
                  </div>
                </td>

                {/* Inline Sparkline (Center) */}
                <td className="py-2.5 px-2 text-center">
                  <Sparkline data={series} isPositive={ag.returnPct >= 0} />
                </td>

                {/* Net Return (%) (PRIMARY FOCUS: Center, Bold, Upsized, Full-Brightness) */}
                <td className="py-2.5 px-3 text-center">
                  <span
                    className={cn(
                      'font-mono text-sm sm:text-base font-bold tabular-nums',
                      ag.returnPct > 0
                        ? 'text-positive'
                        : ag.returnPct < 0
                        ? 'text-negative'
                        : 'text-zinc-300'
                    )}
                  >
                    {formatPct(ag.returnPct)}
                  </span>
                </td>

                {/* Alpha vs Nifty (%) (SECONDARY: Center, Smaller, Muted Opacity) */}
                <td className="py-2.5 px-3 text-center">
                  <span
                    className={cn(
                      'font-mono text-xs sm:text-sm font-medium tabular-nums',
                      ag.alphaVsBenchmarkPct > 0
                        ? 'text-positive/75'
                        : ag.alphaVsBenchmarkPct < 0
                        ? 'text-negative/75'
                        : 'text-zinc-500'
                    )}
                  >
                    {formatPct(ag.alphaVsBenchmarkPct)}
                  </span>
                </td>

                {/* Portfolio NAV (Center) */}
                <td className="py-2.5 px-3 text-center font-mono text-xs text-zinc-300 tabular-nums">
                  {formatPaiseToRupees(ag.navPaise || 50000000)}
                </td>

                {/* Active Positions (Center) */}
                <td className="py-2.5 px-2 text-center font-mono text-xs tabular-nums text-zinc-300">
                  {ag.activePositionsCount}
                </td>

                {/* Closed Trades (Center) */}
                <td className="py-2.5 px-2 text-center font-mono text-xs tabular-nums text-zinc-400">
                  {ag.closedTrades}
                  {ag.isProvisional && (
                    <span className="text-[10px] text-zinc-500 ml-1">/ 30</span>
                  )}
                </td>

                {/* Sharpe Ratio (Center) - Reusable Warmup Treatment */}
                {!isCompact && (
                  <>
                    <td className="py-2.5 px-2.5 text-center font-mono text-xs text-zinc-400 tabular-nums">
                      <WarmupMetric
                        value={ag.sharpeRatio}
                        closedTrades={ag.closedTrades}
                        formatter={(v) => v.toFixed(2)}
                        compact
                      />
                    </td>

                    {/* Max Drawdown (Center) - Reusable Warmup Treatment */}
                    <td className="py-2.5 px-2.5 text-center font-mono text-xs text-zinc-400 tabular-nums">
                      <WarmupMetric
                        value={ag.maxDrawdownPct}
                        closedTrades={ag.closedTrades}
                        formatter={(v) => formatPct(v, false)}
                        compact
                      />
                    </td>

                    {/* Win Rate (Center) - Reusable Warmup Treatment */}
                    <td className="py-2.5 px-2.5 text-center font-mono text-xs text-zinc-400 tabular-nums">
                      <WarmupMetric
                        value={ag.winRatePct}
                        closedTrades={ag.closedTrades}
                        formatter={(v) => formatPct(v || 0, false)}
                        compact
                      />
                    </td>
                  </>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>

      {/* Single Footnote: Clean, Institutional, Noise-Free */}
      <div className="px-4 py-2 border-t border-border-hairline bg-[#121212] text-[12px] font-mono text-zinc-500 flex flex-wrap items-center justify-between gap-2">
        <span>* Returns and Alpha are benchmarked against ₹5,00,000 initial seed capital per agent.</span>
        <span>Metrics marked 'Warming up' require 30 closed trades for statistical validity.</span>
      </div>
    </div>
  );
}

export default memo(BenchmarkMatrixTableComponent);
