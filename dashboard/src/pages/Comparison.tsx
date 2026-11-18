import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  Brain,
  Cpu,
  TrendingUp,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  Cell,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  CartesianGrid,
} from 'recharts';
import type { BaselineComparison, AgentLeaderboardEntry } from '../types';
import { apiService, getIsMockMode, TELEMETRY_POLL_INTERVAL_MS } from '../services/api';
import { formatPaiseToRupees, formatPct } from '../utils/formatters';
import { CategoryBadge } from '../components/ui/CategoryBadge';
import { WarmupMetric } from '../components/ui/WarmupMetric';
import { PHILOSOPHY_PAIRS } from '../constants/personas';
import { cn } from '../utils/cn';

export default function Comparison() {
  const [selectedPairId, setSelectedPairId] = useState<string>('simons');
  const [data, setData] = useState<BaselineComparison | null>(null);
  const [liveLeaderboard, setLiveLeaderboard] = useState<AgentLeaderboardEntry[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [isMock] = useState<boolean>(getIsMockMode());
  const [showHorizonTable, setShowHorizonTable] = useState<boolean>(false);

  const currentPair =
    PHILOSOPHY_PAIRS.find((p) => p.id === selectedPairId) || PHILOSOPHY_PAIRS[0];

  useEffect(() => {
    let isSubscribed = true;
    async function fetchComparisonData(isBackground = false) {
      if (!isBackground) setLoading(true);
      try {
        const [compData, boardData] = await Promise.all([
          apiService.getBaselineComparison(currentPair.id),
          apiService.getLeaderboard(),
        ]);
        if (isSubscribed) {
          setData(compData);
          setLiveLeaderboard(boardData);
        }
      } catch (err) {
        console.warn('Failed to load baseline comparison:', err);
      } finally {
        if (isSubscribed && !isBackground) setLoading(false);
      }
    }

    fetchComparisonData(false);

    // Dynamic background polling on synchronized cadence (10 min)
    const pollInterval = setInterval(() => {
      fetchComparisonData(true);
    }, TELEMETRY_POLL_INTERVAL_MS);

    return () => {
      isSubscribed = false;
      clearInterval(pollInterval);
    };
  }, [currentPair.id, isMock]);

  if (loading || !data) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-28 flex justify-center items-center">
        <div className="flex items-center gap-3 text-zinc-500 font-mono text-xs sm:text-sm">
          <div className="w-4 h-4 border-2 border-brand-blue border-t-transparent rounded-full animate-spin" />
          <span>Synchronizing symmetric benchmark telemetry...</span>
        </div>
      </div>
    );
  }

  // Bind live returns from live backend leaderboard
  const liveLlm = liveLeaderboard.find((a) => a.id === currentPair.llmId);
  const liveRules = liveLeaderboard.find((a) => a.id === currentPair.rulesId);

  const effectiveLlmReturn = liveLlm?.returnPct ?? 0;
  const effectiveRulesReturn = liveRules?.returnPct ?? 0;
  const alphaSpreadPct = effectiveLlmReturn - effectiveRulesReturn;

  const llmNav = liveLlm?.navPaise ?? 50000000;
  const rulesNav = liveRules?.navPaise ?? 50000000;
  const niftyNav = data?.nifty500?.benchmarkNavPaise ?? 50000000;

  const llmSharpe = liveLlm?.sharpeRatio ?? 0;
  const rulesSharpe = liveRules?.sharpeRatio ?? 0;

  const llmMaxDd = liveLlm?.maxDrawdownPct ?? 0;
  const rulesMaxDd = liveRules?.maxDrawdownPct ?? 0;
  const niftyMaxDd = data?.nifty500?.maxDrawdownPct ?? 0;

  const llmWinRate = liveLlm?.winRatePct ?? 0;
  const rulesWinRate = liveRules?.winRatePct ?? 0;

  const llmTrades = liveLlm?.closedTrades ?? 0;
  const rulesTrades = liveRules?.closedTrades ?? 0;

  // Chart data: Net Cognitive Alpha Diverging Bars (LLM - Rules)
  const divergingChartData = data.horizonReturns.map((hr) => {
    const buyVal = hr.llmBuyAvgPct ?? hr.llmSimonsBuyAvgPct ?? 0;
    const rulesVal = hr.rulesBuyAvgPct ?? hr.rulesSimonsBuyAvgPct ?? 0;
    const niftyVal = hr.nifty500AvgPct ?? 0;
    const holdVal = hr.llmHoldAvgPct ?? hr.llmSimonsHoldAvgPct ?? 0;
    const alphaVal = Number((buyVal - rulesVal).toFixed(2));

    return {
      horizon: `${hr.horizonDays}d`,
      horizonLabel: `${hr.horizonDays} Trading Days`,
      cognitiveAlpha: alphaVal,
      llmBuy: buyVal,
      rulesBuy: rulesVal,
      niftyVal,
      holdVal,
    };
  });

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-7 animate-hero-entrance font-sans">

      {/* 1. STANDARDIZED MATCHUP HEADER & PHILOSOPHY SWITCHER */}
      <div className="space-y-4 border-b border-border-hairline pb-4">
        <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-4">

          {/* Matchup Identity */}
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-2.5">
              <h1 className="text-2xl sm:text-3xl font-display font-medium tracking-tight text-white">
                {currentPair.llmDisplayName}
              </h1>
              <CategoryBadge type="LLM" />
              <span className="text-zinc-500 font-mono text-sm font-normal">vs.</span>
              <span className="text-xl sm:text-2xl font-display font-medium text-zinc-300">
                {currentPair.rulesDisplayName}
              </span>
              <CategoryBadge type="RULES" />
            </div>
          </div>

          {/* Compact 5-Philosophy Switcher */}
          <div
            role="tablist"
            aria-label="Philosophy matchup pairs"
            className="flex items-center p-0.5 rounded-md bg-surface-well border border-border-hairline text-xs sm:text-sm font-mono flex-shrink-0"
          >
            {PHILOSOPHY_PAIRS.map((pair) => (
              <button
                key={pair.id}
                role="tab"
                aria-selected={selectedPairId === pair.id}
                onClick={() => setSelectedPairId(pair.id)}
                className={cn(
                  "px-3 py-1.5 rounded transition-colors cursor-pointer text-xs sm:text-sm",
                  selectedPairId === pair.id
                    ? "bg-brand-blue-soft text-brand-blue-text font-semibold border border-brand-blue/40"
                    : "text-zinc-400 hover:text-white border border-transparent"
                )}
              >
                {pair.shortLabel}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* 2. SYMMETRIC PERFORMANCE MATRIX: DELTA AS HERO (HIGH LEGIBILITY) */}
      <div className="glow-box rounded-lg">
      <div className="overflow-x-auto border border-border-hairline bg-[#161616] rounded-lg">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-border-hairline text-zinc-400 text-xs sm:text-sm font-mono bg-[#121212] whitespace-nowrap">
              <th className="py-3 px-3.5 font-normal">Metric</th>
              <th className="py-3 px-3.5 font-normal text-right text-zinc-300">
                <div className="flex items-center justify-end gap-1.5">
                  <Brain className="w-4 h-4 text-zinc-400" />
                  <span>{currentPair.llmDisplayName}</span>
                  <CategoryBadge type="LLM" />
                </div>
              </th>
              <th className="py-3 px-3.5 font-normal text-right text-zinc-300">
                <div className="flex items-center justify-end gap-1.5">
                  <Cpu className="w-4 h-4 text-zinc-400" />
                  <span>{currentPair.rulesDisplayName}</span>
                  <CategoryBadge type="RULES" />
                </div>
              </th>
              <th className="py-3 px-3.5 font-normal text-right text-zinc-400">
                <div className="flex items-center justify-end gap-1.5">
                  <TrendingUp className="w-4 h-4 text-zinc-500" />
                  <span>Nifty 500</span>
                </div>
              </th>
              {/* Visual Hero Column: Brand Blue Highlighted Header with Left Divider */}
              <th className="py-3 px-3.5 font-semibold text-right text-brand-blue-text border-l border-border-hairline bg-brand-blue-soft/20">
                Cognitive Delta
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border-hairline text-base font-sans whitespace-nowrap">

            {/* Cumulative Return */}
            <tr className="transition-colors group hover:bg-white/[0.03]">
              <td className="py-3 px-3.5 font-sans font-medium text-white text-base">Cumulative Return</td>
              <td className={cn("py-3 px-3.5 text-right font-mono font-bold text-base tabular-nums", effectiveLlmReturn >= 0 ? "text-positive" : "text-negative")}>
                {formatPct(effectiveLlmReturn)}
              </td>
              <td className={cn("py-3 px-3.5 text-right font-mono font-bold text-base tabular-nums", effectiveRulesReturn >= 0 ? "text-positive" : "text-negative")}>
                {formatPct(effectiveRulesReturn)}
              </td>
              <td className="py-3 px-3.5 text-right font-mono text-zinc-400 font-medium text-sm sm:text-base tabular-nums">
                {formatPct(data?.nifty500?.returnPct ?? 0)}
              </td>
              <td className="py-3 px-3.5 text-right font-mono font-bold text-base sm:text-lg tabular-nums text-brand-blue-text border-l border-border-hairline bg-brand-blue-soft/20">
                {alphaSpreadPct >= 0 ? '+' : ''}{alphaSpreadPct.toFixed(2)}%
              </td>
            </tr>

            {/* Portfolio NAV */}
            <tr className="transition-colors group hover:bg-white/[0.03] bg-white/[0.01]">
              <td className="py-3 px-3.5 font-sans font-medium text-white text-base">Portfolio NAV</td>
              <td className="py-3 px-3.5 text-right font-mono text-base text-zinc-100 font-medium tabular-nums">
                {formatPaiseToRupees(llmNav)}
              </td>
              <td className="py-3 px-3.5 text-right font-mono text-base text-zinc-100 font-medium tabular-nums">
                {formatPaiseToRupees(rulesNav)}
              </td>
              <td className="py-3 px-3.5 text-right font-mono text-base text-zinc-400 font-medium tabular-nums">
                {formatPaiseToRupees(niftyNav)}
              </td>
              <td className="py-3 px-3.5 text-right font-mono font-bold text-base tabular-nums text-brand-blue-text border-l border-border-hairline bg-brand-blue-soft/20">
                {llmNav >= rulesNav ? '+' : ''}{formatPaiseToRupees(llmNav - rulesNav)}
              </td>
            </tr>

            {/* Sharpe Ratio */}
            <tr className="transition-colors group hover:bg-white/[0.03]">
              <td className="py-3 px-3.5 font-sans font-medium text-white text-base">Sharpe Ratio</td>
              <td className="py-3 px-3.5 text-right font-mono text-base text-zinc-100 font-medium tabular-nums">
                <WarmupMetric value={llmSharpe} closedTrades={llmTrades} formatter={(v) => Number(v).toFixed(2)} compact />
              </td>
              <td className="py-3 px-3.5 text-right font-mono text-base text-zinc-100 font-medium tabular-nums">
                <WarmupMetric value={rulesSharpe} closedTrades={rulesTrades} formatter={(v) => Number(v).toFixed(2)} compact />
              </td>
              <td className="py-3 px-3.5 text-right font-mono text-base text-zinc-500 font-normal tabular-nums">—</td>
              <td className="py-3 px-3.5 text-right font-mono font-bold text-base tabular-nums text-brand-blue-text border-l border-border-hairline bg-brand-blue-soft/20">
                {llmTrades >= 30 && rulesTrades >= 30 ? (
                  `${llmSharpe >= rulesSharpe ? '+' : ''}${(llmSharpe - rulesSharpe).toFixed(2)}`
                ) : (
                  <span className="text-zinc-600 font-mono text-base" title="Warming up: requires 30 closed trades">—</span>
                )}
              </td>
            </tr>

            {/* Max Drawdown */}
            <tr className="transition-colors group hover:bg-white/[0.03] bg-white/[0.01]">
              <td className="py-3 px-3.5 font-sans font-medium text-white text-base">Max Drawdown</td>
              <td className="py-3 px-3.5 text-right font-mono text-base text-negative font-medium tabular-nums">
                -{Math.abs(llmMaxDd).toFixed(2)}%
              </td>
              <td className="py-3 px-3.5 text-right font-mono text-base text-negative font-medium tabular-nums">
                -{Math.abs(rulesMaxDd).toFixed(2)}%
              </td>
              <td className="py-3 px-3.5 text-right font-mono text-base text-zinc-400 font-medium tabular-nums">
                -{Math.abs(niftyMaxDd).toFixed(2)}%
              </td>
              <td className="py-3 px-3.5 text-right font-mono font-bold text-base tabular-nums text-brand-blue-text border-l border-border-hairline bg-brand-blue-soft/20">
                {llmMaxDd <= rulesMaxDd ? '+' : '-'}{Math.abs(llmMaxDd - rulesMaxDd).toFixed(2)}%
              </td>
            </tr>

            {/* Win Rate */}
            <tr className="transition-colors group hover:bg-white/[0.03]">
              <td className="py-3 px-3.5 font-sans font-medium text-white text-base">Trade Win Rate</td>
              <td className="py-3 px-3.5 text-right font-mono text-base text-zinc-100 font-medium tabular-nums">
                <WarmupMetric value={llmWinRate} closedTrades={llmTrades} formatter={(v) => `${Number(v).toFixed(1)}%`} compact />
              </td>
              <td className="py-3 px-3.5 text-right font-mono text-base text-zinc-100 font-medium tabular-nums">
                <WarmupMetric value={rulesWinRate} closedTrades={rulesTrades} formatter={(v) => `${Number(v).toFixed(1)}%`} compact />
              </td>
              <td className="py-3 px-3.5 text-right font-mono text-base text-zinc-500 font-normal tabular-nums">—</td>
              <td className="py-3 px-3.5 text-right font-mono font-bold text-base tabular-nums text-brand-blue-text border-l border-border-hairline bg-brand-blue-soft/20">
                {llmTrades >= 30 && rulesTrades >= 30 ? (
                  `${llmWinRate >= rulesWinRate ? '+' : ''}${(llmWinRate - rulesWinRate).toFixed(1)}%`
                ) : (
                  <span className="text-zinc-600 font-mono text-base" title="Warming up: requires 30 closed trades">—</span>
                )}
              </td>
            </tr>

            {/* Closed Trades */}
            <tr className="transition-colors group hover:bg-white/[0.03] bg-white/[0.01]">
              <td className="py-3 px-3.5 font-sans font-medium text-white text-base">Closed Trades</td>
              <td className="py-3 px-3.5 text-right font-mono text-base text-zinc-100 font-medium tabular-nums">{llmTrades}</td>
              <td className="py-3 px-3.5 text-right font-mono text-base text-zinc-100 font-medium tabular-nums">{rulesTrades}</td>
              <td className="py-3 px-3.5 text-right font-mono text-base text-zinc-500 font-normal tabular-nums">—</td>
              <td className="py-3 px-3.5 text-right font-mono font-bold text-base tabular-nums text-brand-blue-text border-l border-border-hairline bg-brand-blue-soft/20">
                {llmTrades - rulesTrades >= 0 ? '+' : ''}{llmTrades - rulesTrades}
              </td>
            </tr>

          </tbody>
        </table>
      </div>
      </div>

      {/* 3. NET COGNITIVE ALPHA DIVERGING BAR CHART */}
      <div className="glow-box border border-border-hairline bg-surface-inset rounded-lg p-5 sm:p-6 space-y-5">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2 border-b border-border-hairline pb-4">
          <div>
            <h3 className="font-display font-medium text-base sm:text-lg text-white">
              Net Cognitive Alpha by Holding Horizon
            </h3>
            <p className="text-xs sm:text-sm text-zinc-400 font-mono mt-1">
              LLM return % - Rules return %
            </p>
          </div>

          <div className="flex items-center gap-2">
            <span className="px-3 py-1.5 rounded font-mono text-sm bg-brand-blue-soft text-brand-blue-text border border-brand-blue/40 font-semibold">
              Cognitive Δ: {alphaSpreadPct >= 0 ? '+' : ''}{alphaSpreadPct.toFixed(2)}%
            </span>
          </div>
        </div>

        {/* Primary Diverging Bar Chart */}
        <div className="w-full h-64 pt-2 min-h-[260px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={divergingChartData}
              margin={{ top: 15, right: 20, left: 0, bottom: 5 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
              <XAxis
                dataKey="horizon"
                stroke="#71717a"
                fontSize={13}
                fontFamily="JetBrains Mono"
                tickLine={false}
              />
              <YAxis
                stroke="#71717a"
                fontSize={12}
                tickFormatter={(v) => `${v > 0 ? '+' : ''}${v}%`}
                fontFamily="JetBrains Mono"
                tickLine={false}
                axisLine={false}
              />
              <ReferenceLine y={0} stroke="rgba(255,255,255,0.25)" strokeWidth={1} />
              <Tooltip
                content={({ active, payload }) => {
                  if (!active || !payload || !payload.length) return null;
                  const item = payload[0].payload;
                  return (
                    <div className="bg-[#161616] border border-border-hairline p-3.5 rounded shadow-xl font-mono text-sm space-y-2">
                      <div className="text-zinc-200 font-semibold border-b border-border-hairline pb-1.5 text-sm">
                        Horizon: {item.horizonLabel}
                      </div>
                      <div className="flex justify-between gap-5">
                        <span className="text-zinc-400">LLM Return:</span>
                        <span className="text-white font-medium tabular-nums">{item.llmBuy.toFixed(2)}%</span>
                      </div>
                      <div className="flex justify-between gap-5">
                        <span className="text-zinc-400">Rules Return:</span>
                        <span className="text-zinc-200 font-medium tabular-nums">{item.rulesBuy.toFixed(2)}%</span>
                      </div>
                      <div className="flex justify-between gap-5 pt-1.5 border-t border-border-hairline">
                        <span className="text-brand-blue-text font-semibold">Net Cognitive Alpha:</span>
                        <span className={cn("font-bold tabular-nums text-base", item.cognitiveAlpha >= 0 ? "text-positive" : "text-negative")}>
                          {item.cognitiveAlpha >= 0 ? '+' : ''}{item.cognitiveAlpha.toFixed(2)}%
                        </span>
                      </div>
                      <div className="flex justify-between gap-5 text-zinc-400 text-xs">
                        <span>Nifty 500 Index:</span>
                        <span className="tabular-nums">{item.niftyVal.toFixed(2)}%</span>
                      </div>
                    </div>
                  );
                }}
              />
              <Bar dataKey="cognitiveAlpha" radius={[2, 2, 0, 0]}>
                {divergingChartData.map((entry, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={entry.cognitiveAlpha >= 0 ? '#10B981' : '#F43F5E'}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Legend / Quick Read Aid */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pt-2 border-t border-border-hairline font-mono text-xs sm:text-sm text-zinc-300">
          <div className="flex items-center gap-5">
            <span className="inline-flex items-center gap-2">
              <span className="w-3 h-3 rounded-sm bg-[#10B981]" />
              <span className="text-xs sm:text-sm text-zinc-400 font-mono mt-1">Positive Alpha (LLM Beats Rules)</span>
            </span>
            <span className="inline-flex items-center gap-2">
              <span className="w-3 h-3 rounded-sm bg-[#F43F5E]" />
              <span className="text-xs sm:text-sm text-zinc-400 font-mono mt-1">Negative Alpha (Rules Beat LLM)</span>
            </span>
          </div>
        </div>

        {/* Collapsible Horizon Drawer */}
        <div className="pt-2 border-t border-border-hairline space-y-3 font-mono text-xs sm:text-sm">
          <div className="flex items-center justify-between">
            <button
              onClick={() => setShowHorizonTable(!showHorizonTable)}
              aria-expanded={showHorizonTable}
              className="inline-flex items-center gap-2 text-zinc-300 hover:text-white transition-colors cursor-pointer text-xs sm:text-sm font-medium"
            >
              <span>{showHorizonTable ? 'Hide Detailed Horizon Figures' : 'View Detailed Horizon Figures (5 Windows)'}</span>
              {showHorizonTable ? <ChevronUp className="w-4 h-4 text-zinc-400" /> : <ChevronDown className="w-4 h-4 text-zinc-400" />}
            </button>
          </div>

          {showHorizonTable && (
            <div className="overflow-x-auto border border-border-hairline bg-[#161616] rounded-lg mt-3 animate-hero-entrance">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-border-hairline text-zinc-400 text-xs sm:text-sm font-mono bg-[#121212] whitespace-nowrap">
                    <th className="py-3 px-3.5 font-normal">Holding Horizon</th>
                    <th className="py-3 px-3.5 text-right font-normal text-positive">LLM BUY Avg</th>
                    <th className="py-3 px-3.5 text-right font-normal text-sky-400">Rules BUY Avg</th>
                    <th className="py-3 px-3.5 text-right font-semibold text-brand-blue-text">Net Cognitive Alpha</th>
                    <th className="py-3 px-3.5 text-right font-normal text-zinc-400">LLM HOLD Avg</th>
                    <th className="py-3 px-3.5 text-right font-normal text-zinc-400">Nifty 500</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border-hairline text-base font-sans whitespace-nowrap">
                  {data.horizonReturns.map((hr, idx) => {
                    const buyVal = hr.llmBuyAvgPct ?? hr.llmSimonsBuyAvgPct ?? 0;
                    const holdVal = hr.llmHoldAvgPct ?? hr.llmSimonsHoldAvgPct ?? 0;
                    const rulesVal = hr.rulesBuyAvgPct ?? hr.rulesSimonsBuyAvgPct ?? 0;
                    const niftyVal = hr.nifty500AvgPct ?? 0;
                    const alphaVal = buyVal - rulesVal;

                    return (
                      <tr
                        key={hr.horizonDays}
                        className={cn(
                          "transition-colors group hover:bg-white/[0.03]",
                          idx % 2 === 1 ? "bg-white/[0.01]" : "bg-transparent"
                        )}
                      >
                        <td className="py-3 px-3.5 font-sans font-medium text-white text-base">
                          {hr.horizonDays} Trading Days
                        </td>
                        <td className="py-3 px-3.5 text-right font-mono font-bold text-base text-positive tabular-nums">
                          {formatPct(buyVal)}
                        </td>
                        <td className="py-3 px-3.5 text-right font-mono text-sm sm:text-base text-sky-400 font-medium tabular-nums">
                          {formatPct(rulesVal)}
                        </td>
                        <td className={cn("py-3 px-3.5 text-right font-mono font-bold text-base tabular-nums", alphaVal >= 0 ? "text-brand-blue-text" : "text-negative")}>
                          {alphaVal >= 0 ? '+' : ''}{alphaVal.toFixed(2)}%
                        </td>
                        <td className="py-3 px-3.5 text-right font-mono text-sm sm:text-base text-zinc-300 font-normal tabular-nums">
                          {formatPct(holdVal)}
                        </td>
                        <td className="py-3 px-3.5 text-right font-mono text-sm sm:text-base text-zinc-400 font-normal tabular-nums">
                          {formatPct(niftyVal)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* 4. FOOTER AUDIT LINK TO AGENT TERMINAL */}
      <div className="border border-border-hairline bg-surface-inset rounded-lg p-5 flex flex-col sm:flex-row items-center justify-between gap-4 font-mono text-xs">
        <div className="flex items-center gap-2.5 text-zinc-300 font-sans">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          <span>Every cited numeric indicator is audited against raw exchange snapshots in the individual Agent Terminal.</span>
        </div>
        <Link
          to={`/portfolio/${currentPair.personaKey}`}
          className="text-xs font-mono text-brand-blue-text hover:underline flex items-center gap-1.5 flex-shrink-0"
        >
          <span>Open {currentPair.llmDisplayName} Audit Ledger</span>
          <span>→</span>
        </Link>
      </div>
    </div>
  );
}
