import { memo } from 'react';
import { Link } from 'react-router-dom';
import type { AgentLeaderboardEntry, NavHistoryPoint } from '../types';
import { formatPaiseToRupees, formatPct } from '../utils/formatters';
import { CategoryBadge } from './ui/CategoryBadge';
import { WarmupMetric } from './ui/WarmupMetric';
import { getAgentDisplayName, isRulesStrategy } from '../constants/personas';
import { cn } from '../utils/cn';

interface BenchmarkMatrixTableProps {
  agents: AgentLeaderboardEntry[];
  navHistory?: NavHistoryPoint[];
  isCompact?: boolean;
  showRiskMetrics?: boolean;
}

function formatStrategyName(agent: AgentLeaderboardEntry): { name: string; isRules: boolean } {
  const isRules = isRulesStrategy(agent.id) || isRulesStrategy(agent.name);
  const name = getAgentDisplayName(agent.id || agent.name);
  return { name, isRules };
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
  showRiskMetrics = false,
}: BenchmarkMatrixTableProps) {
  // Sort by return descending for clear leaderboard ranking
  const sorted = [...agents].sort((a, b) => b.returnPct - a.returnPct);
  const rows = isCompact ? sorted.slice(0, 5) : sorted;

  return (
    <div className="glow-box rounded-lg">
    <div className="overflow-x-auto border border-border-hairline bg-[#161616] rounded-lg">
      <table className="w-full text-left border-collapse">
        {/* Table Header: whitespace-nowrap prevents two-row wrap */}
        <thead>
          <tr className="border-b border-border-hairline text-zinc-400 text-xs sm:text-sm font-mono bg-[#121212] whitespace-nowrap">
            <th className="py-2.5 px-2 font-normal w-10 text-center text-zinc-500 whitespace-nowrap">Rank</th>
            <th className="py-2.5 px-2.5 font-normal min-w-[150px] text-left whitespace-nowrap">Agents</th>
            <th className="py-2.5 px-2 text-center font-normal min-w-[65px] whitespace-nowrap">Trajectory</th>
            <th className="py-2.5 px-2.5 text-right font-semibold min-w-[95px] text-white whitespace-nowrap">
              Net Return (%)
            </th>
            <th className="py-2.5 px-2.5 text-right font-normal min-w-[95px] text-zinc-400 whitespace-nowrap">
              Alpha vs Nifty (%)
            </th>
            <th className="py-2.5 px-2.5 text-right font-normal min-w-[105px] text-zinc-400 whitespace-nowrap">
              NAV (INR)
            </th>
            <th className="py-2.5 px-2 text-right font-normal min-w-[55px] text-zinc-400 whitespace-nowrap">
              Open Pos
            </th>
            <th className="py-2.5 px-2 text-right font-normal min-w-[55px] text-zinc-400 whitespace-nowrap">
              Trades
            </th>
            {!isCompact && showRiskMetrics && (
              <>
                <th className="py-2.5 px-2.5 text-right font-normal min-w-[70px] text-zinc-400 whitespace-nowrap">Sharpe</th>
                <th className="py-2.5 px-2.5 text-right font-normal min-w-[75px] text-zinc-400 whitespace-nowrap">Max DD</th>
                <th className="py-2.5 px-2.5 text-right font-normal min-w-[75px] text-zinc-400 whitespace-nowrap">Win Rate</th>
              </>
            )}
          </tr>
        </thead>

        {/* Rows: Clear hierarchy with bold Return and muted supporting metrics */}
        <tbody className="divide-y divide-border-hairline text-base font-sans whitespace-nowrap">
          {rows.length === 0 ? (
            <tr>
              <td colSpan={isCompact || !showRiskMetrics ? 8 : 11} className="py-8 text-center text-zinc-500 font-mono text-sm">
                No active strategy records available.
              </td>
            </tr>
          ) : (
            rows.map((ag, idx) => {
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
                        'font-mono text-sm sm:text-base tabular-nums',
                        isRankOne ? 'text-white font-bold' : 'text-zinc-500'
                      )}
                    >
                      {idx < 9 ? `0${idx + 1}` : idx + 1}
                    </span>
                  </td>

                  {/* Strategy Name (Left Aligned for Readability) */}
                  <td className="py-2.5 px-2.5 text-left">
                    <div className="flex items-center gap-2">
                      <Link
                        to={`/portfolio/${ag.id}`}
                        className="font-sans font-medium text-base text-zinc-100 hover:text-brand-blue-text transition-colors truncate max-w-[170px]"
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

                  {/* Net Return (%) (PRIMARY: Right-aligned, Bold, Full-Brightness) */}
                  <td className="py-2.5 px-2.5 text-right">
                    <span
                      className={cn(
                        'font-mono text-base font-bold tabular-nums',
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

                  {/* Alpha vs Nifty (%) (SECONDARY: Right-aligned, Muted Opacity) */}
                  <td className="py-2.5 px-2.5 text-right">
                    <span
                      className={cn(
                        'font-mono text-base font-medium tabular-nums',
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

                  {/* Portfolio NAV (Right-aligned) */}
                  <td className="py-2.5 px-2.5 text-right font-mono text-base text-zinc-300 tabular-nums">
                    {formatPaiseToRupees(ag.navPaise || 50000000)}
                  </td>

                  {/* Active Positions (Right-aligned) */}
                  <td className="py-2.5 px-2 text-right font-mono text-base tabular-nums text-zinc-300">
                    {ag.activePositionsCount}
                  </td>

                  {/* Closed Trades (Right-aligned) */}
                  <td className="py-2.5 px-2 text-right font-mono text-base tabular-nums text-zinc-400">
                    {ag.closedTrades}
                    {ag.isProvisional && (
                      <span className="text-xs text-zinc-500 ml-1">/ 30</span>
                    )}
                  </td>

                  {/* Sharpe, Max DD, Win Rate (Option C: Controlled by showRiskMetrics toggle) */}
                  {!isCompact && showRiskMetrics && (
                    <>
                      <td className="py-2.5 px-2.5 text-right font-mono text-base text-zinc-400 tabular-nums">
                        <WarmupMetric
                          value={ag.sharpeRatio}
                          closedTrades={ag.closedTrades}
                          formatter={(v) => v.toFixed(2)}
                          compact
                        />
                      </td>

                      <td className="py-2.5 px-2.5 text-right font-mono text-base text-zinc-400 tabular-nums">
                        <WarmupMetric
                          value={ag.maxDrawdownPct}
                          closedTrades={ag.closedTrades}
                          formatter={(v) => formatPct(v, false)}
                          compact
                        />
                      </td>

                      <td className="py-2.5 px-2.5 text-right font-mono text-base text-zinc-400 tabular-nums">
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
            }))}
        </tbody>
      </table>

      {/* Single Footnote: Clean, Institutional, Noise-Free */}
      <div className="px-4 py-2.5 border-t border-border-hairline bg-[#121212] text-xs sm:text-sm font-mono text-zinc-500 flex flex-wrap items-center justify-between gap-2">
        <span>* Returns are benchmarked against ₹5L seed capital per agent.</span>
        <span>{showRiskMetrics ? "Risk metrics marked '—' require 30 closed trades for statistical validity." : "Toggle 'Risk Stats' to inspect Sharpe, Max Drawdown, and Win Rates."}</span>
      </div>
    </div>
    </div>
  );
}

export default memo(BenchmarkMatrixTableComponent);
