import { useState, useEffect, useRef } from 'react';
import type { CSSProperties } from 'react';
import { Link } from 'react-router-dom';
import {
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
import { formatPaiseToRupees } from '../utils/formatters';
import { CategoryBadge } from '../components/ui/CategoryBadge';
import { getAgentLabel } from '../lib/agentNames';
import { useIntroDone } from '../hooks/useIntro';
import { useCountUp } from '../hooks/useCountUp';
import { usePrefersReducedMotion } from '../hooks/usePrefersReducedMotion';
import PageTitle from '../components/ui/PageTitle';
import AgentSwitchDropdown from '../components/AgentSwitchDropdown';
import { cn } from '../utils/cn';

/** The 5 LLM/Rules pairs, keyed by the same base persona key used throughout the Agent
 * Terminal (Portfolio.tsx's basePersonaKey / AgentSwitchDropdown's ids). Ids are the real
 * backend agent ids. */
const PAIR_MAP: Record<string, { llmId: string; rulesId: string }> = {
  simons: { llmId: 'simons', rulesId: 'baseline-simons-rules' },
  lynch: { llmId: 'lynch', rulesId: 'baseline-lynch-rules' },
  marks: { llmId: 'marks', rulesId: 'baseline-marks-rules' },
  jhunjhunwala: { llmId: 'jhunjhunwala', rulesId: 'baseline-rj-rules' },
  varsity: { llmId: 'varsity', rulesId: 'baseline-varsity-rules' },
};

function baseKeyForAgentId(id: string): string {
  const normalized = id === 'stockminds-core' ? 'varsity' : id;
  const found = Object.entries(PAIR_MAP).find(
    ([, v]) => v.llmId === normalized || v.rulesId === normalized
  );
  return found ? found[0] : 'simons';
}

const COUNT_OPTS = { duration: 1300, delay: 250 };
const SESSION_KEY_PREFIX = 'stockminds_compare_count_';

const fmtPctSigned = (n: number) => `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`;
const fmtMaxDD = (n: number) => `-${n.toFixed(2)}%`;
const fmtCount = (n: number) => `${Math.round(n)}`;
const fmtDiffCount = (n: number) => `${n >= 0 ? '+' : ''}${Math.round(n)}`;
const fmtSharpe = (n: number) => n.toFixed(2);
const fmtDiffSharpe = (n: number) => `${n >= 0 ? '+' : ''}${n.toFixed(2)}`;
const fmtWinRate = (n: number) => `${n.toFixed(1)}%`;

interface MetricConfig {
  key: string;
  label: string;
  llmValue: number | null;
  rulesValue: number | null;
  format: (n: number) => string;
  diffValue: number | null;
  diffFormat: (n: number) => string;
}

/** One value that counts up from 0 once this pair's animation has started, shows the live
 * value instantly on a later refresh or a repeat visit, and "—" for a missing value. */
function CountSpan({
  value,
  format,
  eligible,
  started,
  className,
}: {
  value: number | null;
  format: (n: number) => string;
  eligible: boolean;
  started: boolean;
  className?: string;
}) {
  const gated = value === null ? undefined : (eligible ? (started ? value : undefined) : value);
  const text = useCountUp(gated, format, COUNT_OPTS);
  if (value === null) return <span className={cn(className, 'text-zinc-500')}>&mdash;</span>;
  return <span className={className}>{eligible ? text : format(value)}</span>;
}

/** One paired bar (either the AI agent's or the Rules twin's) for one metric: the fill grows
 * from 0 to its final width once, in sync with `filled`, and the value counts up in sync
 * with `started` -- both driven by the parent PairedComparisonBody. */
function MetricBarRow({
  value,
  maxAbs,
  variant,
  format,
  eligible,
  started,
  filled,
}: {
  value: number | null;
  maxAbs: number;
  variant: 'green' | 'cream';
  format: (n: number) => string;
  eligible: boolean;
  started: boolean;
  filled: boolean;
}) {
  if (value === null) {
    return (
      <div className="comparison-bar-row">
        <div className="comparison-bar-track" />
        <span className="comparison-bar-value text-zinc-500">&mdash;</span>
      </div>
    );
  }
  const pct = maxAbs > 0 ? Math.min(100, (Math.abs(value) / maxAbs) * 100) : 0;
  return (
    <div className="comparison-bar-row">
      <div className="comparison-bar-track">
        <div
          className={cn(
            'comparison-bar-fill',
            variant === 'green' ? 'comparison-bar-fill--green' : 'comparison-bar-fill--cream'
          )}
          style={{
            width: `max(2px, ${pct}%)`,
            transform: filled ? 'scaleX(1)' : 'scaleX(0)',
            transformOrigin: 'left',
            transition: eligible ? 'transform 1.4s cubic-bezier(0.22, 1, 0.36, 1)' : 'none',
          }}
        />
      </div>
      <span className="comparison-bar-value">
        <CountSpan value={value} format={format} eligible={eligible} started={started} />
      </span>
    </div>
  );
}

interface PairedComparisonBodyProps {
  pairId: string;
  llmName: string;
  rulesName: string;
  metrics: MetricConfig[];
  llmNavPaise: number | null;
  rulesNavPaise: number | null;
  niftyNavPaise: number | null;
  introDone: boolean;
}

/**
 * Owns the first-open-per-pair count-up/bar-grow animation. Remounted fresh per pair (see
 * `key={pairId}` at the call site) so every piece of state below starts over for a new pair
 * via ordinary lazy initial state -- no reset-in-effect needed.
 *
 * `eligible`: decided once at mount from sessionStorage (+ reduced motion) and never changes.
 * `started`: flips true (and *that's* when sessionStorage is actually written) once the page
 * is mounted, the intro is done, and the tab is visible -- re-checked on visibilitychange so
 * a pair opened in a background tab plays when you switch to it, never while hidden.
 */
function PairedComparisonBody({
  pairId,
  llmName,
  rulesName,
  metrics,
  llmNavPaise,
  rulesNavPaise,
  niftyNavPaise,
  introDone,
}: PairedComparisonBodyProps) {
  const reducedMotion = usePrefersReducedMotion();
  const [eligible] = useState(() => {
    if (reducedMotion) return false;
    try {
      return sessionStorage.getItem(`${SESSION_KEY_PREFIX}${pairId}`) !== 'true';
    } catch {
      return false;
    }
  });
  const [started, setStarted] = useState(false);
  const startedRef = useRef(false);

  useEffect(() => {
    if (!eligible) return;
    let cancelled = false;
    function tryStart() {
      if (cancelled || startedRef.current) return;
      if (introDone && document.visibilityState === 'visible') {
        startedRef.current = true;
        try {
          sessionStorage.setItem(`${SESSION_KEY_PREFIX}${pairId}`, 'true');
        } catch {
          /* ignore */
        }
        setStarted(true);
      }
    }
    const timeoutId = window.setTimeout(tryStart, 0);
    document.addEventListener('visibilitychange', tryStart);
    return () => {
      cancelled = true;
      window.clearTimeout(timeoutId);
      document.removeEventListener('visibilitychange', tryStart);
    };
  }, [eligible, introDone, pairId]);

  const [barFilled, setBarFilled] = useState(!eligible);
  useEffect(() => {
    if (!started) return;
    const id = window.setTimeout(() => setBarFilled(true), 450);
    return () => window.clearTimeout(id);
  }, [started]);

  return (
    <div className="glow-box border border-border-hairline bg-surface-inset rounded-lg p-5 sm:p-6 space-y-1">
      {metrics.map((m) => {
        const maxAbs = Math.max(Math.abs(m.llmValue ?? 0), Math.abs(m.rulesValue ?? 0));
        return (
          <div key={m.key} className="comparison-metric-row">
            <div className="comparison-metric-row__label">{m.label}</div>
            <div className="comparison-metric-row__bars">
              <MetricBarRow value={m.llmValue} maxAbs={maxAbs} variant="green" format={m.format} eligible={eligible} started={started} filled={barFilled} />
              <MetricBarRow value={m.rulesValue} maxAbs={maxAbs} variant="cream" format={m.format} eligible={eligible} started={started} filled={barFilled} />
            </div>
            <div className="comparison-metric-row__diff">
              <CountSpan value={m.diffValue} format={m.diffFormat} eligible={eligible} started={started} />
            </div>
          </div>
        );
      })}

      <div className="pt-3 mt-2 border-t border-border-hairline font-mono text-[13px] text-zinc-400 flex flex-wrap items-center gap-x-2 gap-y-1">
        <span className="text-zinc-300">Portfolio NAV</span>
        <span>{llmName}</span>
        <CountSpan value={llmNavPaise} format={formatPaiseToRupees} eligible={eligible} started={started} className="text-zinc-200" />
        <span>{rulesName}</span>
        <CountSpan value={rulesNavPaise} format={formatPaiseToRupees} eligible={eligible} started={started} className="text-zinc-200" />
        <span>Nifty</span>
        <CountSpan value={niftyNavPaise} format={formatPaiseToRupees} eligible={eligible} started={started} className="text-zinc-200" />
      </div>

      <div className="pt-3 flex items-center gap-5 font-mono text-xs text-zinc-400">
        <span className="inline-flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: 'var(--alloc-invested-to)' }} />
          {llmName} (AI)
        </span>
        <span className="inline-flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: 'var(--alloc-cash)' }} />
          {rulesName}
        </span>
      </div>
    </div>
  );
}

export default function Comparison() {
  const [selectedPairId, setSelectedPairId] = useState<string>('simons');
  const [data, setData] = useState<BaselineComparison | null>(null);
  const [liveLeaderboard, setLiveLeaderboard] = useState<AgentLeaderboardEntry[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [fetchError, setFetchError] = useState<boolean>(false);
  const [isMock] = useState<boolean>(getIsMockMode());
  const [showHorizonTable, setShowHorizonTable] = useState<boolean>(false);
  const introDone = useIntroDone();

  const pair = PAIR_MAP[selectedPairId] || PAIR_MAP.simons;
  const llmName = getAgentLabel(pair.llmId);
  const rulesName = getAgentLabel(pair.rulesId);

  useEffect(() => {
    let isSubscribed = true;
    async function fetchComparisonData(isBackground = false) {
      if (!isBackground) {
        setLoading(true);
        setFetchError(false);
      }
      try {
        const [compData, boardData] = await Promise.all([
          apiService.getBaselineComparison(pair.llmId),
          apiService.getLeaderboard(),
        ]);
        if (isSubscribed) {
          setData(compData);
          setLiveLeaderboard(boardData);
        }
      } catch (err) {
        console.warn('Failed to load baseline comparison:', err);
        if (isSubscribed && !isBackground) setFetchError(true);
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
  }, [pair.llmId, isMock]);

  if (fetchError) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-28 flex flex-col items-center justify-center gap-4">
        <div className="text-zinc-400 font-mono text-sm">Could not load the comparison data.</div>
        <button
          onClick={() => {
            setFetchError(false);
            setLoading(true);
            setSelectedPairId((id) => id);
            // Re-trigger the effect by toggling a dependency-equivalent state isn't needed --
            // the effect already re-runs fetchComparisonData on mount; force it directly:
            apiService.getBaselineComparison(pair.llmId).then((compData) => {
              setData(compData);
              setLoading(false);
            }).catch(() => {
              setFetchError(true);
              setLoading(false);
            });
          }}
          className="px-4 py-2 rounded font-mono text-sm text-brand-blue-text border border-brand-blue/40 bg-brand-blue-soft hover:bg-brand-blue-soft/70 transition-colors cursor-pointer"
        >
          Retry
        </button>
      </div>
    );
  }

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
  const liveLlm = liveLeaderboard.find((a) => a.id === pair.llmId);
  const liveRules = liveLeaderboard.find((a) => a.id === pair.rulesId);

  const llmReturn = liveLlm?.returnPct ?? null;
  const rulesReturn = liveRules?.returnPct ?? null;
  const alphaSpreadPct = (llmReturn ?? 0) - (rulesReturn ?? 0);

  const llmNav = liveLlm?.navPaise ?? null;
  const rulesNav = liveRules?.navPaise ?? null;
  const niftyNav = data?.nifty500?.benchmarkNavPaise ?? null;

  const llmTrades = liveLlm?.closedTrades ?? null;
  const rulesTrades = liveRules?.closedTrades ?? null;
  const bothWarmedUp = (llmTrades ?? 0) >= 30 && (rulesTrades ?? 0) >= 30;

  const llmSharpe = bothWarmedUp ? (liveLlm?.sharpeRatio ?? null) : null;
  const rulesSharpe = bothWarmedUp ? (liveRules?.sharpeRatio ?? null) : null;

  const llmMaxDd = liveLlm?.maxDrawdownPct != null ? Math.abs(liveLlm.maxDrawdownPct) : null;
  const rulesMaxDd = liveRules?.maxDrawdownPct != null ? Math.abs(liveRules.maxDrawdownPct) : null;

  const llmWinRate = bothWarmedUp ? (liveLlm?.winRatePct ?? null) : null;
  const rulesWinRate = bothWarmedUp ? (liveRules?.winRatePct ?? null) : null;

  const metrics: MetricConfig[] = [
    {
      key: 'return',
      label: 'Cumulative Return',
      llmValue: llmReturn,
      rulesValue: rulesReturn,
      format: fmtPctSigned,
      diffValue: llmReturn != null && rulesReturn != null ? llmReturn - rulesReturn : null,
      diffFormat: fmtPctSigned,
    },
    {
      key: 'maxdd',
      label: 'Max Drawdown',
      llmValue: llmMaxDd,
      rulesValue: rulesMaxDd,
      format: fmtMaxDD,
      diffValue: llmMaxDd != null && rulesMaxDd != null ? rulesMaxDd - llmMaxDd : null,
      diffFormat: fmtPctSigned,
    },
    {
      key: 'trades',
      label: 'Closed Trades',
      llmValue: llmTrades,
      rulesValue: rulesTrades,
      format: fmtCount,
      diffValue: llmTrades != null && rulesTrades != null ? llmTrades - rulesTrades : null,
      diffFormat: fmtDiffCount,
    },
    {
      key: 'winrate',
      label: 'Trade Win Rate',
      llmValue: llmWinRate,
      rulesValue: rulesWinRate,
      format: fmtWinRate,
      diffValue: llmWinRate != null && rulesWinRate != null ? llmWinRate - rulesWinRate : null,
      diffFormat: fmtPctSigned,
    },
    {
      key: 'sharpe',
      label: 'Sharpe Ratio',
      llmValue: llmSharpe,
      rulesValue: rulesSharpe,
      format: fmtSharpe,
      diffValue: llmSharpe != null && rulesSharpe != null ? llmSharpe - rulesSharpe : null,
      diffFormat: fmtDiffSharpe,
    },
  ];

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

      {/* 1. MATCHUP HEADER & Compare-agent dropdown */}
      <div className="space-y-4 border-b border-border-hairline pb-4">
        <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-4">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
            <PageTitle
              as="span"
              text={llmName}
              style={{ '--fs': '38px', fontSize: 'clamp(26px, 4vw, 38px)' } as CSSProperties}
            >
              {llmName}
            </PageTitle>
            <CategoryBadge type="LLM" />
            <span className="text-zinc-500 font-mono text-sm">vs.</span>
            <PageTitle
              as="span"
              text={rulesName}
              style={{ '--fs': '38px', fontSize: 'clamp(26px, 4vw, 38px)' } as CSSProperties}
            >
              {rulesName}
            </PageTitle>
            <CategoryBadge type="RULES" />
          </div>

          <div className="w-full sm:w-[220px] flex-shrink-0">
            <AgentSwitchDropdown
              triggerLabel="Compare agent"
              highlightIds={[pair.llmId, pair.rulesId]}
              onSelect={(id) => setSelectedPairId(baseKeyForAgentId(id))}
              leaderboard={liveLeaderboard}
            />
          </div>
        </div>
      </div>

      {/* 2. PAIRED METRIC BARS */}
      <PairedComparisonBody
        key={pair.llmId}
        pairId={pair.llmId}
        llmName={llmName}
        rulesName={rulesName}
        metrics={metrics}
        llmNavPaise={llmNav}
        rulesNavPaise={rulesNav}
        niftyNavPaise={niftyNav}
        introDone={introDone}
      />

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
                          {buyVal.toFixed(2)}%
                        </td>
                        <td className="py-3 px-3.5 text-right font-mono text-sm sm:text-base text-sky-400 font-medium tabular-nums">
                          {rulesVal.toFixed(2)}%
                        </td>
                        <td className={cn("py-3 px-3.5 text-right font-mono font-bold text-base tabular-nums", alphaVal >= 0 ? "text-brand-blue-text" : "text-negative")}>
                          {alphaVal >= 0 ? '+' : ''}{alphaVal.toFixed(2)}%
                        </td>
                        <td className="py-3 px-3.5 text-right font-mono text-sm sm:text-base text-zinc-300 font-normal tabular-nums">
                          {holdVal.toFixed(2)}%
                        </td>
                        <td className="py-3 px-3.5 text-right font-mono text-sm sm:text-base text-zinc-400 font-normal tabular-nums">
                          {niftyVal.toFixed(2)}%
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
          to={`/portfolio/${pair.llmId}`}
          className="text-xs font-mono text-brand-blue-text hover:underline flex items-center gap-1.5 flex-shrink-0"
        >
          <span>Open {llmName} Audit Ledger</span>
          <span>→</span>
        </Link>
      </div>
    </div>
  );
}
