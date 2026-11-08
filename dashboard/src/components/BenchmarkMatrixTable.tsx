import { useState } from 'react';
import { Link } from 'react-router-dom';
import { HelpCircle } from 'lucide-react';
import type { AgentLeaderboardEntry } from '../types';
import { formatPaiseToRupees, formatPct } from '../utils/formatters';

interface BenchmarkMatrixTableProps {
  agents: AgentLeaderboardEntry[];
  isCompact?: boolean;
}

function formatStrategyName(agent: AgentLeaderboardEntry): { name: string; isRules: boolean } {
  const isRules =
    agent.id.startsWith('baseline-') ||
    agent.id.includes('rules') ||
    agent.name.toLowerCase().includes('rules');

  // Strip redundant text like "(LLM)", "(Rules Control)", "(Rules Baseline)"
  let clean = agent.name
    .replace(/\s*\((LLM|Rules Control|Rules Baseline|Rules|Algorithmic Control Benchmark)\)/gi, '')
    .trim();

  // If rules baseline, format as "Baseline: <clean>"
  if (isRules) {
    clean = clean.replace(/^baseline[-:\s]*/i, '');
    return { name: `Baseline: ${clean}`, isRules: true };
  }

  return { name: clean, isRules: false };
}

export default function BenchmarkMatrixTable({
  agents,
  isCompact = false,
}: BenchmarkMatrixTableProps) {
  const [showThresholds, setShowThresholds] = useState(false);

  // Sort by return descending for clear leaderboard ranking
  const sorted = [...agents].sort((a, b) => b.returnPct - a.returnPct);
  const rows = isCompact ? sorted.slice(0, 5) : sorted;

  return (
    <div className="overflow-x-auto cosmic-card rounded-xl">
      <table className="w-full text-left border-collapse">
        {/* Table Header: Clean sans-serif, quiet borders, right-aligned metrics */}
        <thead>
          <tr className="border-b border-white/[0.08] text-zinc-400 text-xs font-sans uppercase tracking-wider bg-white/[0.03]">
            <th className="py-3 px-3 font-medium w-14 text-center text-zinc-500">Rank</th>
            <th className="py-3 px-4 font-medium min-w-[220px]">Strategy</th>

            {/* Net Return explicitly stating percentage */}
            <th className="py-3 px-4 text-right font-medium min-w-[120px]">
              Net Return (%)
            </th>

            <th className="py-3 px-4 text-right font-medium min-w-[120px]">Δ vs Nifty (%)</th>
            <th className="py-3 px-4 text-right font-medium min-w-[90px]">Sharpe</th>
            <th className="py-3 px-4 text-right font-medium min-w-[90px]">Max DD (%)</th>
            <th className="py-3 px-4 text-right font-medium min-w-[100px]">Win Rate (%)</th>

            {!isCompact && (
              <>
                <th className="py-3 px-4 text-right font-medium min-w-[130px]">Portfolio NAV</th>
                <th className="py-3 px-3 text-center font-medium min-w-[90px]">Trades</th>
              </>
            )}
          </tr>
        </thead>

        {/* Rows: Uniform intensity magnitude across all metrics */}
        <tbody className="divide-y divide-white/[0.04] text-sm font-sans">
          {rows.map((ag, idx) => {
            const { name: displayName, isRules } = formatStrategyName(ag);
            const isZebra = idx % 2 === 1;
            const tradesCount = ag.closedTrades || ag.totalTrades || 0;
            const isProvisional = ag.isProvisional ?? (tradesCount < 30);
            const isPreSeason = tradesCount === 0 && ag.returnPct === 0;

            return (
              <tr
                key={ag.id}
                className={`transition-colors group hover:bg-white/[0.04] ${
                  isZebra ? 'bg-white/[0.015]' : 'bg-transparent'
                }`}
              >
                {/* Uniform Tabular Rank Numerals */}
                <td className="py-3 px-3 text-center">
                  <span className="font-mono text-xs text-zinc-500 tabular-nums">
                    {idx < 9 ? `0${idx + 1}` : idx + 1}
                  </span>
                </td>

                {/* Strategy Name with Categorical Color Badges */}
                <td className="py-3 px-4">
                  <div className="flex items-center gap-2.5">
                    <Link
                      to={`/portfolio/${ag.id}`}
                      className="font-sans font-medium text-[14px] text-zinc-100 hover:text-white transition-colors truncate max-w-[220px]"
                    >
                      {displayName}
                    </Link>

                    {/* Categorical Engine Badge: Amber outline for LLM, Slate outline for Rules */}
                    {isRules ? (
                      <span className="px-1.5 py-0.5 text-[10px] font-mono tracking-wider border border-slate-600/40 text-slate-300 bg-slate-500/10 rounded font-medium flex-shrink-0">
                        Rules
                      </span>
                    ) : (
                      <span className="px-1.5 py-0.5 text-[10px] font-mono tracking-wider border border-amber-500/30 text-amber-300 bg-amber-500/10 rounded font-medium flex-shrink-0">
                        LLM
                      </span>
                    )}
                  </div>
                </td>

                {/* Net Return (%) (Quiet dash if pre-season, uniform color if active) */}
                <td className="py-3 px-4 text-right">
                  {isPreSeason ? (
                    <span className="font-mono text-sm text-zinc-500 tabular-nums">—</span>
                  ) : (
                    <span
                      className={`font-mono text-sm tabular-nums ${
                        ag.returnPct > 0
                          ? 'text-emerald-400 font-medium'
                          : ag.returnPct < 0
                          ? 'text-rose-400 font-medium'
                          : 'text-zinc-300 font-normal'
                      }`}
                    >
                      {formatPct(ag.returnPct)}
                    </span>
                  )}
                </td>

                {/* Δ vs Nifty (%) (Quiet dash if pre-season, uniform color if active) */}
                <td className="py-3 px-4 text-right">
                  {isPreSeason ? (
                    <span className="font-mono text-sm text-zinc-500 tabular-nums">—</span>
                  ) : (
                    <span
                      className={`font-mono text-sm tabular-nums ${
                        ag.alphaVsBenchmarkPct > 0
                          ? 'text-emerald-400 font-medium'
                          : ag.alphaVsBenchmarkPct < 0
                          ? 'text-rose-400 font-medium'
                          : 'text-zinc-400 font-normal'
                      }`}
                    >
                      {formatPct(ag.alphaVsBenchmarkPct)}
                    </span>
                  )}
                </td>

                {/* Sharpe Ratio (Quiet dash if pre-season) */}
                <td className="py-3 px-4 text-right font-mono text-sm tabular-nums">
                  {isPreSeason ? (
                    <span className="font-mono text-sm text-zinc-500 tabular-nums">—</span>
                  ) : (
                    <span
                      className={
                        ag.sharpeRatio >= 1.0
                          ? 'text-emerald-400 font-medium'
                          : ag.sharpeRatio < 0
                          ? 'text-rose-400 font-medium'
                          : 'text-zinc-300 font-normal'
                      }
                    >
                      {ag.sharpeRatio.toFixed(2)}
                    </span>
                  )}
                </td>

                {/* Max Drawdown (%) (NEVER GREEN. Quiet dash if pre-season) */}
                <td className="py-3 px-4 text-right font-mono text-sm tabular-nums">
                  {isPreSeason ? (
                    <span className="font-mono text-sm text-zinc-500 tabular-nums">—</span>
                  ) : (
                    <span
                      className={
                        ag.maxDrawdownPct >= 15.0
                          ? 'text-rose-400 font-medium'
                          : ag.maxDrawdownPct >= 10.0
                          ? 'text-zinc-300 font-normal'
                          : 'text-zinc-400 font-normal'
                      }
                    >
                      {formatPct(ag.maxDrawdownPct, false)}
                    </span>
                  )}
                </td>

                {/* Win Rate (%) (Quiet dash if pre-season) */}
                <td className="py-3 px-4 text-right font-mono text-sm tabular-nums">
                  {isPreSeason ? (
                    <span className="font-mono text-sm text-zinc-500 tabular-nums">—</span>
                  ) : (
                    <span
                      className={
                        (ag.winRatePct || 0) >= 50.0
                          ? 'text-emerald-400 font-medium'
                          : (ag.winRatePct || 0) < 40.0 && (ag.winRatePct || 0) > 0
                          ? 'text-rose-400 font-medium'
                          : 'text-zinc-300 font-normal'
                      }
                    >
                      {formatPct(ag.winRatePct || 0, false)}
                    </span>
                  )}
                </td>

                {/* Portfolio NAV */}
                {!isCompact && (
                  <>
                    <td className="py-3 px-4 text-right font-mono text-sm tabular-nums text-zinc-300 font-normal">
                      {formatPaiseToRupees(ag.navPaise || 50000000)}
                    </td>

                    {/* Trades Count & Provisional Status Pill */}
                    <td className="py-3 px-3 text-center font-mono text-sm tabular-nums">
                      <span className="text-zinc-300">
                        {tradesCount}
                      </span>
                      {isProvisional && (
                        <span className="block sm:inline-block sm:ml-1.5 mt-0.5 sm:mt-0 px-1.5 py-0.2 text-[9px] font-mono uppercase tracking-wider border border-amber-500/30 text-amber-400 bg-amber-500/10 rounded font-medium align-middle">
                          Provisional
                        </span>
                      )}
                    </td>
                  </>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>

      {/* Metric Thresholds Affordance: Kept Behind (?) Click/Hover Reveal */}
      <div className="px-4 py-2 border-t border-white/[0.06] bg-[#0F0F12] flex flex-wrap items-center justify-between text-xs font-sans gap-2">
        <button
          type="button"
          onClick={() => setShowThresholds(!showThresholds)}
          onMouseEnter={() => setShowThresholds(true)}
          className="inline-flex items-center gap-1.5 text-zinc-500 hover:text-zinc-300 transition-colors cursor-pointer py-0.5 font-sans text-xs focus:outline-none"
          title="Click or hover to reveal metric coloring rules"
        >
          <HelpCircle className="w-3.5 h-3.5 text-zinc-500" />
          <span className="font-mono text-[11px]">Metric Thresholds</span>
          <span className="text-[10px] text-zinc-600 font-mono">({showThresholds ? 'Hide' : 'Show'})</span>
        </button>

        {showThresholds && (
          <div className="flex flex-wrap items-center gap-1.5 text-[11px] font-mono animate-hero-entrance">
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-white/[0.02] border border-white/[0.06] text-zinc-300">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
              Return &gt;0%
            </span>
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-white/[0.02] border border-white/[0.06] text-zinc-300">
              <span className="w-1.5 h-1.5 rounded-full bg-rose-400" />
              Return &lt;0%
            </span>
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-white/[0.02] border border-white/[0.06] text-zinc-300">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
              Sharpe &ge;1.0
            </span>
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-white/[0.02] border border-white/[0.06] text-zinc-300">
              <span className="w-1.5 h-1.5 rounded-full bg-rose-400" />
              Sharpe &lt;0
            </span>
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-white/[0.02] border border-white/[0.06] text-zinc-300">
              <span className="w-1.5 h-1.5 rounded-full bg-rose-400" />
              Max DD &ge;15%
            </span>
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-white/[0.02] border border-white/[0.06] text-zinc-300">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
              Win Rate &ge;50%
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
