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
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
} from 'recharts';
import type { BaselineComparison, AgentLeaderboardEntry } from '../types';
import { apiService, getIsMockMode, TELEMETRY_POLL_INTERVAL_MS } from '../services/api';
import { formatPaiseToRupees, formatPct } from '../utils/formatters';
import { SectionHeader } from '../components/ui/SectionHeader';
import { CategoryBadge } from '../components/ui/CategoryBadge';
import SmallSampleNotice from '../components/SmallSampleNotice';
import ExplainabilitySpotlight from '../components/ExplainabilitySpotlight';
import { cn } from '../utils/cn';

interface PhilosophyPair {
  id: string;
  personaKey: string;
  name: string;
  llmId: string;
  rulesId: string;
  llmDisplayName: string;
  rulesDisplayName: string;
  school: string;
  horizon: string;
  coreHypothesis: string;
}

const PHILOSOPHY_PAIRS: PhilosophyPair[] = [
  {
    id: 'simons',
    personaKey: 'simons',
    name: 'Quantitative Momentum',
    llmId: 'simons',
    rulesId: 'baseline-simons-rules',
    llmDisplayName: 'Jim Simons',
    rulesDisplayName: 'Simons Rules Baseline',
    school: 'Statistical Momentum & Volatility Parity',
    horizon: '1–10 Days',
    coreHypothesis: 'Can dynamic volatility sizing and momentum adaptation beat static 2.5x ATR trailing stops?',
  },
  {
    id: 'varsity',
    personaKey: 'varsity',
    name: 'Dual-Confluence Swing',
    llmId: 'varsity',
    rulesId: 'baseline-varsity-rules',
    llmDisplayName: 'StockMinds Core',
    rulesDisplayName: 'Varsity Rules Baseline',
    school: 'Zerodha Varsity Confluence · Solvency DCF + EMA Momentum',
    horizon: '5–20 Days',
    coreHypothesis: 'Can contextual synthesis combine balance-sheet conservatism with technical entry timing more cleanly than rigid sequential hurdles?',
  },
  {
    id: 'lynch',
    personaKey: 'lynch',
    name: 'GARP Compounding',
    llmId: 'lynch',
    rulesId: 'baseline-lynch-rules',
    llmDisplayName: 'Peter Lynch',
    rulesDisplayName: 'Lynch Rules Baseline',
    school: 'GARP Framework · PEG Ratio <= 1.0 · Durable ROCE Growth',
    horizon: '15–60 Days',
    coreHypothesis: 'Can narrative evaluation distinguish genuine multi-quarter operating margin expansion from cyclical value traps?',
  },
  {
    id: 'marks',
    personaKey: 'marks',
    name: 'Contrarian Value',
    llmId: 'marks',
    rulesId: 'baseline-marks-rules',
    llmDisplayName: 'Howard Marks',
    rulesDisplayName: 'Marks Rules Baseline',
    school: 'Second-Level Thinking · Cyclical Distress · Margin of Safety',
    horizon: '30–90 Days',
    coreHypothesis: 'Can second-level thinking identify whether a 52-week low represents forced institutional liquidation or terminal solvency impairment?',
  },
  {
    id: 'jhunjhunwala',
    personaKey: 'jhunjhunwala',
    name: 'Secular Domestic Growth',
    llmId: 'jhunjhunwala',
    rulesId: 'baseline-rj-rules',
    llmDisplayName: 'Rakesh Jhunjhunwala',
    rulesDisplayName: 'Jhunjhunwala Rules Baseline',
    school: 'Structural Compounding · Promoter Skin-in-the-game · Capex Leaders',
    horizon: '90–180 Days',
    coreHypothesis: 'Can thematic conviction comfortably absorb interim drawdown volatility to pyramid into secular India capex winners?',
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
        <div className="flex items-center gap-3 text-zinc-500 font-mono text-xs">
          <div className="w-4 h-4 border-2 border-accent border-t-transparent rounded-full animate-spin" />
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

  // Chart data for forward return horizon breakdown
  const chartData = data.horizonReturns.map((hr) => ({
    horizon: `${hr.horizonDays}d`,
    [`${currentPair.llmDisplayName} (BUY)`]: hr.llmBuyAvgPct ?? hr.llmSimonsBuyAvgPct ?? 0,
    [`${currentPair.llmDisplayName} (HOLD)`]: hr.llmHoldAvgPct ?? hr.llmSimonsHoldAvgPct ?? 0,
    [`${currentPair.rulesDisplayName} (BUY)`]: hr.rulesBuyAvgPct ?? hr.rulesSimonsBuyAvgPct ?? 0,
    'Nifty 500 Index': hr.nifty500AvgPct ?? 0,
  }));

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-7 animate-hero-entrance font-sans">
      
      {/* 1. STANDARDIZED PAGE HEADER & PAIR SELECTOR */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 border-b border-border-hairline pb-4">
        <SectionHeader
          title="Cognitive Alpha Benchmark"
          tag="SYMMETRIC DELTA AUDIT"
          subtitle="Direct comparison isolating cognitive LLM inference against deterministic Python rules on identical candidates."
        />

        {/* Strategy Selector Tabs */}
        <div className="flex items-center p-0.5 rounded bg-[#121212] border border-border-hairline text-xs font-mono overflow-x-auto max-w-full">
          {PHILOSOPHY_PAIRS.map((pair) => (
            <button
              key={pair.id}
              onClick={() => setSelectedPairId(pair.id)}
              className={cn(
                "px-3 py-1.5 rounded transition-colors cursor-pointer whitespace-nowrap",
                selectedPairId === pair.id
                  ? "bg-white/10 text-accent font-semibold"
                  : "text-zinc-400 hover:text-white"
              )}
            >
              {pair.name}
            </button>
          ))}
        </div>
      </div>

      {/* 2. PHILOSOPHY BRIEFING BAR */}
      <div className="border border-border-hairline bg-[#161616] rounded-lg p-3 sm:px-4 flex flex-wrap items-center justify-between gap-3 font-mono text-xs">
        <div className="flex flex-wrap items-center gap-2.5">
          <span className="px-2 py-0.5 rounded bg-white/[0.04] text-zinc-200 border border-border-hairline text-[11px] font-semibold uppercase">
            {currentPair.name}
          </span>
          <span className="text-zinc-600">·</span>
          <span className="text-zinc-400">Horizon: <strong className="text-zinc-200 font-normal">{currentPair.horizon}</strong></span>
          <span className="text-zinc-600">·</span>
          <span className="text-zinc-400">{currentPair.school}</span>
        </div>

        {/* Cognitive Spread Metric */}
        <div className="flex items-center gap-2 text-xs">
          <span className="text-zinc-500 uppercase text-[10px]">Net Cognitive Delta:</span>
          <span className={cn("font-bold tabular-nums text-sm sm:text-base", alphaSpreadPct >= 0 ? "text-accent" : "text-negative")}>
            {alphaSpreadPct >= 0 ? '+' : ''}{alphaSpreadPct.toFixed(2)}%
          </span>
        </div>
      </div>

      {/* Provisional Sample Notice */}
      <SmallSampleNotice closedTradesCount={llmTrades} threshold={30} />

      {/* 3. SYMMETRIC PERFORMANCE MATRIX: DELTA AS HERO */}
      <div className="border border-border-hairline bg-[#161616] rounded-lg overflow-hidden">
        <div className="px-4 py-3 bg-[#121212] border-b border-border-hairline flex items-center justify-between font-mono text-xs">
          <span className="uppercase tracking-wider text-zinc-400 font-semibold">
            Symmetric Performance Matrix
          </span>
          <span className="text-[11px] text-zinc-500">
            Identical Market Inputs · ₹5,00,000 Starting Seed
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left font-mono text-xs">
            <thead>
              <tr className="bg-[#121212] border-b border-border-hairline text-[11px] text-zinc-400 uppercase tracking-wider">
                <th className="py-3 px-4 font-normal">Metric</th>
                <th className="py-3 px-4 font-normal text-right text-zinc-300">
                  <div className="flex items-center justify-end gap-1.5">
                    <Brain className="w-3.5 h-3.5 text-zinc-400" />
                    <span>{currentPair.llmDisplayName}</span>
                    <CategoryBadge type="LLM" />
                  </div>
                </th>
                <th className="py-3 px-4 font-normal text-right text-zinc-300">
                  <div className="flex items-center justify-end gap-1.5">
                    <Cpu className="w-3.5 h-3.5 text-zinc-400" />
                    <span>{currentPair.rulesDisplayName}</span>
                    <CategoryBadge type="RULES" />
                  </div>
                </th>
                <th className="py-3 px-4 font-normal text-right text-zinc-400">
                  <div className="flex items-center justify-end gap-1.5">
                    <TrendingUp className="w-3.5 h-3.5 text-zinc-500" />
                    <span>Nifty 500</span>
                  </div>
                </th>
                {/* Visual Hero Column: Gold Highlighted Header with Left Divider */}
                <th className="py-3 px-4 font-semibold text-right text-accent border-l border-border-hairline bg-accent/[0.03]">
                  Cognitive Delta
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-hairline text-zinc-300">
              
              {/* Cumulative Return */}
              <tr className="hover:bg-white/[0.02] transition-colors">
                <td className="py-3 px-4 font-sans font-medium text-white">Cumulative Return</td>
                <td className={cn("py-3 px-4 text-right font-normal tabular-nums", effectiveLlmReturn >= 0 ? "text-positive" : "text-negative")}>
                  {formatPct(effectiveLlmReturn)}
                </td>
                <td className={cn("py-3 px-4 text-right font-normal tabular-nums", effectiveRulesReturn >= 0 ? "text-positive" : "text-negative")}>
                  {formatPct(effectiveRulesReturn)}
                </td>
                <td className="py-3 px-4 text-right text-zinc-500 font-normal tabular-nums">
                  {formatPct(data?.nifty500?.returnPct ?? 0)}
                </td>
                <td className="py-3 px-4 text-right font-bold text-sm sm:text-base tabular-nums text-accent border-l border-border-hairline bg-accent/[0.03]">
                  {alphaSpreadPct >= 0 ? '+' : ''}{alphaSpreadPct.toFixed(2)}%
                </td>
              </tr>

              {/* Portfolio NAV */}
              <tr className="hover:bg-white/[0.02] transition-colors">
                <td className="py-3 px-4 font-sans font-medium text-white">Portfolio NAV</td>
                <td className="py-3 px-4 text-right text-zinc-300 font-normal tabular-nums">
                  {formatPaiseToRupees(llmNav)}
                </td>
                <td className="py-3 px-4 text-right text-zinc-300 font-normal tabular-nums">
                  {formatPaiseToRupees(rulesNav)}
                </td>
                <td className="py-3 px-4 text-right text-zinc-500 font-normal tabular-nums">
                  {formatPaiseToRupees(niftyNav)}
                </td>
                <td className="py-3 px-4 text-right font-bold text-sm sm:text-base tabular-nums text-accent border-l border-border-hairline bg-accent/[0.03]">
                  {llmNav >= rulesNav ? '+' : ''}{formatPaiseToRupees(llmNav - rulesNav)}
                </td>
              </tr>

              {/* Sharpe Ratio */}
              <tr className="hover:bg-white/[0.02] transition-colors">
                <td className="py-3 px-4 font-sans font-medium text-white">Sharpe Ratio</td>
                <td className="py-3 px-4 text-right text-zinc-300 font-normal tabular-nums">
                  {llmSharpe.toFixed(2)}
                </td>
                <td className="py-3 px-4 text-right text-zinc-300 font-normal tabular-nums">
                  {rulesSharpe.toFixed(2)}
                </td>
                <td className="py-3 px-4 text-right text-zinc-500 font-normal tabular-nums">—</td>
                <td className="py-3 px-4 text-right font-bold text-sm sm:text-base tabular-nums text-accent border-l border-border-hairline bg-accent/[0.03]">
                  {llmSharpe >= rulesSharpe ? '+' : ''}{(llmSharpe - rulesSharpe).toFixed(2)}
                </td>
              </tr>

              {/* Max Drawdown */}
              <tr className="hover:bg-white/[0.02] transition-colors">
                <td className="py-3 px-4 font-sans font-medium text-white">Max Drawdown</td>
                <td className="py-3 px-4 text-right text-negative font-normal tabular-nums">
                  -{Math.abs(llmMaxDd).toFixed(2)}%
                </td>
                <td className="py-3 px-4 text-right text-negative font-normal tabular-nums">
                  -{Math.abs(rulesMaxDd).toFixed(2)}%
                </td>
                <td className="py-3 px-4 text-right text-zinc-500 font-normal tabular-nums">
                  -{Math.abs(niftyMaxDd).toFixed(2)}%
                </td>
                <td className="py-3 px-4 text-right font-bold text-sm sm:text-base tabular-nums text-accent border-l border-border-hairline bg-accent/[0.03]">
                  {llmMaxDd <= rulesMaxDd ? '+' : '-'}{Math.abs(llmMaxDd - rulesMaxDd).toFixed(2)}%
                </td>
              </tr>

              {/* Win Rate */}
              <tr className="hover:bg-white/[0.02] transition-colors">
                <td className="py-3 px-4 font-sans font-medium text-white">Trade Win Rate</td>
                <td className="py-3 px-4 text-right text-zinc-300 font-normal tabular-nums">
                  {llmWinRate.toFixed(1)}%
                </td>
                <td className="py-3 px-4 text-right text-zinc-300 font-normal tabular-nums">
                  {rulesWinRate.toFixed(1)}%
                </td>
                <td className="py-3 px-4 text-right text-zinc-500 font-normal tabular-nums">—</td>
                <td className="py-3 px-4 text-right font-bold text-sm sm:text-base tabular-nums text-accent border-l border-border-hairline bg-accent/[0.03]">
                  {llmWinRate >= rulesWinRate ? '+' : ''}{(llmWinRate - rulesWinRate).toFixed(1)}%
                </td>
              </tr>

              {/* Closed Trades */}
              <tr className="hover:bg-white/[0.02] transition-colors">
                <td className="py-3 px-4 font-sans font-medium text-white">Closed Trades</td>
                <td className="py-3 px-4 text-right text-zinc-300 font-normal tabular-nums">{llmTrades}</td>
                <td className="py-3 px-4 text-right text-zinc-300 font-normal tabular-nums">{rulesTrades}</td>
                <td className="py-3 px-4 text-right text-zinc-500 font-normal tabular-nums">—</td>
                <td className="py-3 px-4 text-right font-bold text-sm sm:text-base tabular-nums text-accent border-l border-border-hairline bg-accent/[0.03]">
                  {llmTrades - rulesTrades >= 0 ? '+' : ''}{llmTrades - rulesTrades}
                </td>
              </tr>

            </tbody>
          </table>
        </div>
      </div>

      {/* 4. FORWARD-RETURN BAR CHART + COLLAPSIBLE HORIZON BREAKDOWN */}
      <div className="border border-border-hairline bg-[#161616] rounded-lg p-5 sm:p-6 space-y-4">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2 border-b border-border-hairline pb-3">
          <div>
            <h3 className="font-serif font-medium text-base sm:text-lg text-white">
              Forward-Return Trajectory by Holding Horizon
            </h3>
            <p className="text-xs text-zinc-400 font-mono">
              Empirical return comparison across forward evaluation windows (1, 5, 10, 20, 60 days)
            </p>
          </div>

          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded font-mono text-[10px] bg-white/[0.04] text-accent border border-accent/30 font-semibold">
              +{(data.candidateSelectionAlpha ?? alphaSpreadPct).toFixed(2)}% Selection Alpha
            </span>
          </div>
        </div>

        {/* Primary Visualization: Recharts Multi-Series Bar Chart */}
        <div className="w-full h-72 pt-1 min-h-[280px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
              <XAxis dataKey="horizon" stroke="#71717a" fontSize={11} fontFamily="JetBrains Mono" />
              <YAxis stroke="#71717a" fontSize={11} tickFormatter={(v) => `${v}%`} fontFamily="JetBrains Mono" />
              <Tooltip
                formatter={(value: unknown) => [`${Number(value).toFixed(2)}%`, '']}
                contentStyle={{
                  backgroundColor: '#161616',
                  borderColor: 'rgba(255,255,255,0.08)',
                  color: '#FFFFFF',
                  fontSize: '11px',
                  borderRadius: '6px',
                  fontFamily: 'monospace',
                }}
              />
              <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '10px', fontFamily: 'monospace' }} />
              <Bar dataKey={`${currentPair.llmDisplayName} (BUY)`} fill="#10B981" radius={[2, 2, 0, 0]} />
              <Bar dataKey={`${currentPair.llmDisplayName} (HOLD)`} fill="#71717A" radius={[2, 2, 0, 0]} />
              <Bar dataKey={`${currentPair.rulesDisplayName} (BUY)`} fill="#38BDF8" radius={[2, 2, 0, 0]} />
              <Bar dataKey="Nifty 500 Index" fill="#D4AF37" radius={[2, 2, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Collapsible Horizon Table */}
        <div className="pt-2 border-t border-border-hairline space-y-3 font-mono text-xs">
          <div className="flex items-center justify-between">
            <button
              onClick={() => setShowHorizonTable(!showHorizonTable)}
              className="inline-flex items-center gap-1.5 text-zinc-400 hover:text-white transition-colors cursor-pointer text-xs"
            >
              <span>{showHorizonTable ? 'Hide Detailed Horizon Figures' : 'View Detailed Horizon Figures (5 Windows)'}</span>
              {showHorizonTable ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            </button>
            <span className="text-[11px] text-zinc-500">Out-of-sample forward resolution</span>
          </div>

          {showHorizonTable && (
            <div className="overflow-x-auto pt-2 border-t border-border-hairline animate-hero-entrance">
              <table className="w-full text-left text-xs font-mono text-zinc-300">
                <thead className="text-[11px] text-zinc-500 uppercase tracking-wider bg-[#121212]">
                  <tr className="border-b border-border-hairline">
                    <th className="py-2.5 px-3 font-normal">Holding Horizon</th>
                    <th className="py-2.5 px-3 text-right font-normal text-positive">LLM BUY Avg</th>
                    <th className="py-2.5 px-3 text-right font-normal text-zinc-400">LLM HOLD Avg</th>
                    <th className="py-2.5 px-3 text-right font-normal text-accent">Selection Alpha</th>
                    <th className="py-2.5 px-3 text-right font-normal text-sky-400">Rules BUY Avg</th>
                    <th className="py-2.5 px-3 text-right font-normal text-zinc-400">Nifty 500</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border-hairline">
                  {data.horizonReturns.map((hr) => {
                    const buyVal = hr.llmBuyAvgPct ?? hr.llmSimonsBuyAvgPct ?? 0;
                    const holdVal = hr.llmHoldAvgPct ?? hr.llmSimonsHoldAvgPct ?? 0;
                    const rulesVal = hr.rulesBuyAvgPct ?? hr.rulesSimonsBuyAvgPct ?? 0;
                    const niftyVal = hr.nifty500AvgPct ?? 0;
                    const alphaVal = hr.selectionAlphaPct ?? (buyVal - holdVal);

                    return (
                      <tr key={hr.horizonDays} className="hover:bg-white/[0.02] transition-colors">
                        <td className="py-2.5 px-3 font-semibold text-white">
                          {hr.horizonDays} Trading Days
                        </td>
                        <td className="py-2.5 px-3 text-right text-positive font-semibold tabular-nums">
                          {formatPct(buyVal)}
                        </td>
                        <td className="py-2.5 px-3 text-right text-zinc-400 tabular-nums">
                          {formatPct(holdVal)}
                        </td>
                        <td className="py-2.5 px-3 text-right text-accent font-semibold tabular-nums">
                          +{alphaVal.toFixed(2)}%
                        </td>
                        <td className="py-2.5 px-3 text-right text-sky-400 tabular-nums">
                          {formatPct(rulesVal)}
                        </td>
                        <td className="py-2.5 px-3 text-right text-zinc-500 tabular-nums">
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

      {/* 5. EXPLAINABILITY & FAITHFULNESS AUDIT SPOTLIGHT */}
      <ExplainabilitySpotlight personaId={currentPair.personaKey} />
    </div>
  );
}
