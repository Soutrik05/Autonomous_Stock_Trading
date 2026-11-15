import { useState, useEffect } from 'react';
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
import ExplainabilitySpotlight from '../components/ExplainabilitySpotlight';
import { cn } from '../utils/cn';

interface PhilosophyPair {
  id: string;
  personaKey: string;
  name: string;
  shortLabel: string;
  llmId: string;
  rulesId: string;
  llmDisplayName: string;
  rulesDisplayName: string;
  school: string;
  horizon: string;
}

const PHILOSOPHY_PAIRS: PhilosophyPair[] = [
  {
    id: 'simons',
    personaKey: 'simons',
    name: 'Quantitative Momentum',
    shortLabel: 'Simons',
    llmId: 'simons',
    rulesId: 'baseline-simons-rules',
    llmDisplayName: 'Jim Simons',
    rulesDisplayName: 'Simons Rules Baseline',
    school: 'Statistical Momentum & Volatility Parity',
    horizon: '1–10 Days',
  },
  {
    id: 'varsity',
    personaKey: 'varsity',
    name: 'Dual-Confluence Swing',
    shortLabel: 'Core',
    llmId: 'varsity',
    rulesId: 'baseline-varsity-rules',
    llmDisplayName: 'StockMinds Core',
    rulesDisplayName: 'Varsity Rules Baseline',
    school: 'Dual Confluence · Solvency DCF + EMA Momentum',
    horizon: '5–20 Days',
  },
  {
    id: 'lynch',
    personaKey: 'lynch',
    name: 'GARP Compounding',
    shortLabel: 'Lynch',
    llmId: 'lynch',
    rulesId: 'baseline-lynch-rules',
    llmDisplayName: 'Peter Lynch',
    rulesDisplayName: 'Lynch Rules Baseline',
    school: 'GARP Framework · PEG Ratio <= 1.0 · Durable ROCE',
    horizon: '15–60 Days',
  },
  {
    id: 'marks',
    personaKey: 'marks',
    name: 'Contrarian Value',
    shortLabel: 'Marks',
    llmId: 'marks',
    rulesId: 'baseline-marks-rules',
    llmDisplayName: 'Howard Marks',
    rulesDisplayName: 'Marks Rules Baseline',
    school: 'Second-Level Thinking · Cyclical Distress · Margin of Safety',
    horizon: '30–90 Days',
  },
  {
    id: 'jhunjhunwala',
    personaKey: 'jhunjhunwala',
    name: 'Secular Domestic Growth',
    shortLabel: 'Jhunjhunwala',
    llmId: 'jhunjhunwala',
    rulesId: 'baseline-rj-rules',
    llmDisplayName: 'Rakesh Jhunjhunwala',
    rulesDisplayName: 'Jhunjhunwala Rules Baseline',
    school: 'Structural Compounding · Promoter Skin-in-the-Game',
    horizon: '90–180 Days',
  },
];

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
            <p className="text-xs sm:text-sm text-zinc-400 font-mono">
              {currentPair.school} · Horizon: <span className="text-zinc-200">{currentPair.horizon}</span>
            </p>
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

        {/* Orientation Note */}
        <p className="text-sm sm:text-base text-zinc-300 font-sans leading-relaxed max-w-4xl">
          Paired head-to-head evaluation. Both strategies receive identical candidate inputs, starting capital (₹5,00,000), and statutory transaction friction. The single isolated experimental variable is cognition: autonomous generative inference versus deterministic Python rules.
        </p>
      </div>

      {/* 2. SYMMETRIC PERFORMANCE MATRIX: DELTA AS HERO (HIGH LEGIBILITY) */}
      <div className="border border-border-hairline bg-surface-inset rounded-lg overflow-hidden">
        <div className="px-5 py-3.5 bg-surface-well border-b border-border-hairline flex flex-wrap items-center justify-between gap-2 font-mono text-xs sm:text-sm">
          <span className="text-zinc-200 font-medium">
            Symmetric Risk & Return Performance Matrix
          </span>
          <span className="text-xs text-zinc-400">
            Identical Market Inputs · ₹5,00,000 Starting Seed
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left font-mono text-sm sm:text-base">
            <thead>
              <tr className="bg-surface-well border-b border-border-hairline text-xs sm:text-sm text-zinc-400">
                <th className="py-3 px-5 font-normal">Metric</th>
                <th className="py-3 px-5 font-normal text-right text-zinc-300">
                  <div className="flex items-center justify-end gap-1.5">
                    <Brain className="w-4 h-4 text-zinc-400" />
                    <span>{currentPair.llmDisplayName}</span>
                    <CategoryBadge type="LLM" />
                  </div>
                </th>
                <th className="py-3 px-5 font-normal text-right text-zinc-300">
                  <div className="flex items-center justify-end gap-1.5">
                    <Cpu className="w-4 h-4 text-zinc-400" />
                    <span>{currentPair.rulesDisplayName}</span>
                    <CategoryBadge type="RULES" />
                  </div>
                </th>
                <th className="py-3 px-5 font-normal text-right text-zinc-400">
                  <div className="flex items-center justify-end gap-1.5">
                    <TrendingUp className="w-4 h-4 text-zinc-500" />
                    <span>Nifty 500</span>
                  </div>
                </th>
                {/* Visual Hero Column: Brand Blue Highlighted Header with Left Divider */}
                <th className="py-3 px-5 font-semibold text-right text-brand-blue-text border-l border-border-hairline bg-brand-blue-soft/20">
                  Cognitive Delta
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-hairline text-zinc-300">
              
              {/* Cumulative Return */}
              <tr className="hover:bg-white/[0.02] transition-colors">
                <td className="py-3.5 px-5 font-sans font-medium text-white text-sm sm:text-base">Cumulative Return</td>
                <td className={cn("py-3.5 px-5 text-right font-bold text-sm sm:text-base tabular-nums", effectiveLlmReturn >= 0 ? "text-positive" : "text-negative")}>
                  {formatPct(effectiveLlmReturn)}
                </td>
                <td className={cn("py-3.5 px-5 text-right font-bold text-sm sm:text-base tabular-nums", effectiveRulesReturn >= 0 ? "text-positive" : "text-negative")}>
                  {formatPct(effectiveRulesReturn)}
                </td>
                <td className="py-3.5 px-5 text-right text-zinc-400 font-medium text-sm sm:text-base tabular-nums">
                  {formatPct(data?.nifty500?.returnPct ?? 0)}
                </td>
                <td className="py-3.5 px-5 text-right font-bold text-base sm:text-lg tabular-nums text-brand-blue-text border-l border-border-hairline bg-brand-blue-soft/20">
                  {alphaSpreadPct >= 0 ? '+' : ''}{alphaSpreadPct.toFixed(2)}%
                </td>
              </tr>

              {/* Portfolio NAV */}
              <tr className="hover:bg-white/[0.02] transition-colors">
                <td className="py-3.5 px-5 font-sans font-medium text-white text-sm sm:text-base">Portfolio NAV</td>
                <td className="py-3.5 px-5 text-right text-zinc-100 font-medium text-sm sm:text-base tabular-nums">
                  {formatPaiseToRupees(llmNav)}
                </td>
                <td className="py-3.5 px-5 text-right text-zinc-100 font-medium text-sm sm:text-base tabular-nums">
                  {formatPaiseToRupees(rulesNav)}
                </td>
                <td className="py-3.5 px-5 text-right text-zinc-400 font-medium text-sm sm:text-base tabular-nums">
                  {formatPaiseToRupees(niftyNav)}
                </td>
                <td className="py-3.5 px-5 text-right font-bold text-base sm:text-lg tabular-nums text-brand-blue-text border-l border-border-hairline bg-brand-blue-soft/20">
                  {llmNav >= rulesNav ? '+' : ''}{formatPaiseToRupees(llmNav - rulesNav)}
                </td>
              </tr>

              {/* Sharpe Ratio */}
              <tr className="hover:bg-white/[0.02] transition-colors">
                <td className="py-3.5 px-5 font-sans font-medium text-white text-sm sm:text-base">Sharpe Ratio</td>
                <td className="py-3.5 px-5 text-right text-zinc-100 font-medium text-sm sm:text-base tabular-nums">
                  {llmSharpe.toFixed(2)}
                </td>
                <td className="py-3.5 px-5 text-right text-zinc-100 font-medium text-sm sm:text-base tabular-nums">
                  {rulesSharpe.toFixed(2)}
                </td>
                <td className="py-3.5 px-5 text-right text-zinc-500 font-normal text-sm sm:text-base tabular-nums">—</td>
                <td className="py-3.5 px-5 text-right font-bold text-base sm:text-lg tabular-nums text-brand-blue-text border-l border-border-hairline bg-brand-blue-soft/20">
                  {llmSharpe >= rulesSharpe ? '+' : ''}{(llmSharpe - rulesSharpe).toFixed(2)}
                </td>
              </tr>

              {/* Max Drawdown */}
              <tr className="hover:bg-white/[0.02] transition-colors">
                <td className="py-3.5 px-5 font-sans font-medium text-white text-sm sm:text-base">Max Drawdown</td>
                <td className="py-3.5 px-5 text-right text-negative font-medium text-sm sm:text-base tabular-nums">
                  -{Math.abs(llmMaxDd).toFixed(2)}%
                </td>
                <td className="py-3.5 px-5 text-right text-negative font-medium text-sm sm:text-base tabular-nums">
                  -{Math.abs(rulesMaxDd).toFixed(2)}%
                </td>
                <td className="py-3.5 px-5 text-right text-zinc-400 font-medium text-sm sm:text-base tabular-nums">
                  -{Math.abs(niftyMaxDd).toFixed(2)}%
                </td>
                <td className="py-3.5 px-5 text-right font-bold text-base sm:text-lg tabular-nums text-brand-blue-text border-l border-border-hairline bg-brand-blue-soft/20">
                  {llmMaxDd <= rulesMaxDd ? '+' : '-'}{Math.abs(llmMaxDd - rulesMaxDd).toFixed(2)}%
                </td>
              </tr>

              {/* Win Rate */}
              <tr className="hover:bg-white/[0.02] transition-colors">
                <td className="py-3.5 px-5 font-sans font-medium text-white text-sm sm:text-base">Trade Win Rate</td>
                <td className="py-3.5 px-5 text-right text-zinc-100 font-medium text-sm sm:text-base tabular-nums">
                  {llmWinRate.toFixed(1)}%
                </td>
                <td className="py-3.5 px-5 text-right text-zinc-100 font-medium text-sm sm:text-base tabular-nums">
                  {rulesWinRate.toFixed(1)}%
                </td>
                <td className="py-3.5 px-5 text-right text-zinc-500 font-normal text-sm sm:text-base tabular-nums">—</td>
                <td className="py-3.5 px-5 text-right font-bold text-base sm:text-lg tabular-nums text-brand-blue-text border-l border-border-hairline bg-brand-blue-soft/20">
                  {llmWinRate >= rulesWinRate ? '+' : ''}{(llmWinRate - rulesWinRate).toFixed(1)}%
                </td>
              </tr>

              {/* Closed Trades */}
              <tr className="hover:bg-white/[0.02] transition-colors">
                <td className="py-3.5 px-5 font-sans font-medium text-white text-sm sm:text-base">Closed Trades</td>
                <td className="py-3.5 px-5 text-right text-zinc-100 font-medium text-sm sm:text-base tabular-nums">{llmTrades}</td>
                <td className="py-3.5 px-5 text-right text-zinc-100 font-medium text-sm sm:text-base tabular-nums">{rulesTrades}</td>
                <td className="py-3.5 px-5 text-right text-zinc-500 font-normal text-sm sm:text-base tabular-nums">—</td>
                <td className="py-3.5 px-5 text-right font-bold text-base sm:text-lg tabular-nums text-brand-blue-text border-l border-border-hairline bg-brand-blue-soft/20">
                  {llmTrades - rulesTrades >= 0 ? '+' : ''}{llmTrades - rulesTrades}
                </td>
              </tr>

            </tbody>
          </table>
        </div>
      </div>

      {/* 3. NET COGNITIVE ALPHA DIVERGING BAR CHART */}
      <div className="border border-border-hairline bg-surface-inset rounded-lg p-5 sm:p-6 space-y-5">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2 border-b border-border-hairline pb-4">
          <div>
            <h3 className="font-display font-medium text-base sm:text-lg text-white">
              Net Cognitive Alpha by Holding Horizon
            </h3>
            <p className="text-xs sm:text-sm text-zinc-400 font-mono mt-1">
              Empirical outperformance spread (LLM BUY return minus Rules BUY return) across evaluation windows
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
                        <span className="text-zinc-400">LLM BUY Return:</span>
                        <span className="text-white font-medium tabular-nums">{item.llmBuy.toFixed(2)}%</span>
                      </div>
                      <div className="flex justify-between gap-5">
                        <span className="text-zinc-400">Rules BUY Return:</span>
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
              <span className="text-zinc-200 font-medium">Positive Alpha (LLM Beats Rules)</span>
            </span>
            <span className="inline-flex items-center gap-2">
              <span className="w-3 h-3 rounded-sm bg-[#F43F5E]" />
              <span className="text-zinc-200 font-medium">Negative Alpha (Rules Beat LLM)</span>
            </span>
          </div>
          <span className="text-zinc-400">Zero line = Matched Rules Baseline</span>
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
            <span className="text-xs text-zinc-400">Out-of-sample forward resolution</span>
          </div>

          {showHorizonTable && (
            <div className="overflow-x-auto pt-3 border-t border-border-hairline animate-hero-entrance">
              <table className="w-full text-left font-mono text-sm sm:text-base text-zinc-300">
                <thead className="text-xs sm:text-sm text-zinc-400 bg-surface-well">
                  <tr className="border-b border-border-hairline">
                    <th className="py-3 px-4 font-normal">Holding Horizon</th>
                    <th className="py-3 px-4 text-right font-normal text-positive">LLM BUY Avg</th>
                    <th className="py-3 px-4 text-right font-normal text-sky-400">Rules BUY Avg</th>
                    <th className="py-3 px-4 text-right font-normal text-brand-blue-text font-semibold">Net Cognitive Alpha</th>
                    <th className="py-3 px-4 text-right font-normal text-zinc-400">LLM HOLD Avg</th>
                    <th className="py-3 px-4 text-right font-normal text-zinc-400">Nifty 500</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border-hairline">
                  {data.horizonReturns.map((hr) => {
                    const buyVal = hr.llmBuyAvgPct ?? hr.llmSimonsBuyAvgPct ?? 0;
                    const holdVal = hr.llmHoldAvgPct ?? hr.llmSimonsHoldAvgPct ?? 0;
                    const rulesVal = hr.rulesBuyAvgPct ?? hr.rulesSimonsBuyAvgPct ?? 0;
                    const niftyVal = hr.nifty500AvgPct ?? 0;
                    const alphaVal = buyVal - rulesVal;

                    return (
                      <tr key={hr.horizonDays} className="hover:bg-white/[0.02] transition-colors">
                        <td className="py-3 px-4 font-sans font-medium text-white text-sm sm:text-base">
                          {hr.horizonDays} Trading Days
                        </td>
                        <td className="py-3 px-4 text-right text-positive font-bold text-sm sm:text-base tabular-nums">
                          {formatPct(buyVal)}
                        </td>
                        <td className="py-3 px-4 text-right text-sky-400 font-medium text-sm sm:text-base tabular-nums">
                          {formatPct(rulesVal)}
                        </td>
                        <td className={cn("py-3 px-4 text-right font-bold text-sm sm:text-base tabular-nums", alphaVal >= 0 ? "text-brand-blue-text" : "text-negative")}>
                          {alphaVal >= 0 ? '+' : ''}{alphaVal.toFixed(2)}%
                        </td>
                        <td className="py-3 px-4 text-right text-zinc-300 font-normal text-sm sm:text-base tabular-nums">
                          {formatPct(holdVal)}
                        </td>
                        <td className="py-3 px-4 text-right text-zinc-400 font-normal text-sm sm:text-base tabular-nums">
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

      {/* 4. SIMPLIFIED FORENSIC AUDIT & FAITHFULNESS SPOTLIGHT */}
      <ExplainabilitySpotlight personaId={currentPair.personaKey} />
    </div>
  );
}
