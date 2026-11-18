import { useState, useEffect, useRef } from 'react';
import type { CSSProperties, RefObject } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ArrowLeftRight, ChevronDown, ChevronUp } from 'lucide-react';
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
import { getAgentName, LLM_IDS, RULES_IDS } from '../lib/agentNames';
import AgentSwitchDropdown from '../components/AgentSwitchDropdown';
import { useIntroDone } from '../hooks/useIntro';
import { useCountUp } from '../hooks/useCountUp';
import { usePrefersReducedMotion } from '../hooks/usePrefersReducedMotion';
import { cn } from '../utils/cn';

const ALL_AGENT_IDS = [...LLM_IDS, ...RULES_IDS];

/** The 5 LLM/Rules pairs, keyed by the same base persona key used throughout the Agent
 * Terminal. Ids are the real backend agent ids. */
const PAIR_MAP: Record<string, { llmId: string; rulesId: string }> = {
  simons: { llmId: 'simons', rulesId: 'baseline-simons-rules' },
  lynch: { llmId: 'lynch', rulesId: 'baseline-lynch-rules' },
  marks: { llmId: 'marks', rulesId: 'baseline-marks-rules' },
  jhunjhunwala: { llmId: 'jhunjhunwala', rulesId: 'baseline-rj-rules' },
  varsity: { llmId: 'varsity', rulesId: 'baseline-varsity-rules' },
};

function normalizeAgentId(id: string): string {
  return id === 'stockminds-core' ? 'varsity' : id;
}
function isValidAgentId(id: string | null | undefined): id is string {
  return !!id && ALL_AGENT_IDS.includes(normalizeAgentId(id));
}
function baseKeyForAgentId(id: string): string {
  const n = normalizeAgentId(id);
  const found = Object.entries(PAIR_MAP).find(([, v]) => v.llmId === n || v.rulesId === n);
  return found ? found[0] : 'simons';
}
function twinIdOf(id: string): string {
  const n = normalizeAgentId(id);
  const pair = PAIR_MAP[baseKeyForAgentId(n)];
  return n === pair.llmId ? pair.rulesId : pair.llmId;
}
function isRulesId(id: string): boolean {
  return RULES_IDS.includes(normalizeAgentId(id));
}

function getDefaultSlotA(): string {
  try {
    const last = sessionStorage.getItem('stockminds_last_agent');
    if (isValidAgentId(last)) {
      return PAIR_MAP[baseKeyForAgentId(last!)].llmId;
    }
  } catch {
    /* ignore */
  }
  return 'simons';
}

const COUNT_OPTS = { duration: 1300, delay: 250 };
const SESSION_KEY_PREFIX = 'stockminds_compare_';

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
  aValue: number | null;
  bValue: number | null;
  format: (n: number) => string;
  diffValue: number | null;
  diffFormat: (n: number) => string;
}

interface AgentMetrics {
  returnPct: number | null;
  maxDd: number | null;
  trades: number | null;
  winRate: number | null;
  sharpe: number | null;
  nav: number | null;
}

function metricsForAgent(entry: AgentLeaderboardEntry | undefined): AgentMetrics {
  if (!entry) {
    return { returnPct: null, maxDd: null, trades: null, winRate: null, sharpe: null, nav: null };
  }
  const trades = entry.closedTrades ?? null;
  const warmedUp = (trades ?? 0) >= 30;
  return {
    returnPct: entry.returnPct ?? null,
    maxDd: entry.maxDrawdownPct != null ? Math.abs(entry.maxDrawdownPct) : null,
    trades,
    winRate: warmedUp ? (entry.winRatePct ?? null) : null,
    sharpe: warmedUp ? (entry.sharpeRatio ?? null) : null,
    nav: entry.navPaise ?? null,
  };
}

/** One value that counts up from 0 only in 'full' animation mode, shows the live value
 * instantly otherwise (a repeat visit, a later refresh, or reduced motion), and "—" for a
 * missing value. */
function CountSpan({
  value,
  format,
  animate,
  started,
  className,
}: {
  value: number | null;
  format: (n: number) => string;
  animate: boolean;
  started: boolean;
  className?: string;
}) {
  const gated = value === null ? undefined : (animate ? (started ? value : undefined) : value);
  const text = useCountUp(gated, format, COUNT_OPTS);
  if (value === null) return <span className={cn(className, 'text-zinc-500')}>&mdash;</span>;
  return <span className={className}>{animate ? text : format(value)}</span>;
}

function MetricBarRow({
  value,
  maxAbs,
  variant,
  format,
  animate,
  started,
  filled,
  transitionMs,
}: {
  value: number | null;
  maxAbs: number;
  variant: 'green' | 'cream';
  format: (n: number) => string;
  animate: boolean;
  started: boolean;
  filled: boolean;
  transitionMs: number;
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
            transition: transitionMs > 0 ? `transform ${transitionMs}ms cubic-bezier(0.22, 1, 0.36, 1)` : 'none',
          }}
        />
      </div>
      <span className="comparison-bar-value">
        <CountSpan value={value} format={format} animate={animate} started={started} />
      </span>
    </div>
  );
}

interface PairedComparisonBodyProps {
  pairKey: string;
  nameA: string;
  nameB: string;
  metrics: MetricConfig[];
  navA: number | null;
  navB: number | null;
  navNifty: number | null;
  introDone: boolean;
}

/**
 * Owns the per-pair animation. Remounted fresh per pair (`key={pairKey}` at the call site):
 * - Never played this session -> 'full': waits for mount + real data + intro-done + tab-
 *   visible, THEN marks sessionStorage and plays the full 1.3s count-up / 1.4s bar grow.
 * - Already played this session -> 'quick': shows the real numbers immediately, bars just
 *   slide into place over 0.3s (no count-up).
 * - prefers-reduced-motion -> 'none': everything final immediately.
 */
function PairedComparisonBody({
  pairKey,
  nameA,
  nameB,
  metrics,
  navA,
  navB,
  navNifty,
  introDone,
}: PairedComparisonBodyProps) {
  const reducedMotion = usePrefersReducedMotion();
  const [animMode] = useState<'full' | 'quick' | 'none'>(() => {
    if (reducedMotion) return 'none';
    try {
      return sessionStorage.getItem(`${SESSION_KEY_PREFIX}${pairKey}`) === 'true' ? 'quick' : 'full';
    } catch {
      return 'none';
    }
  });
  const animate = animMode === 'full';
  const [started, setStarted] = useState(false);
  const startedRef = useRef(false);

  useEffect(() => {
    if (!animate) return;
    let cancelled = false;
    function tryStart() {
      if (cancelled || startedRef.current) return;
      if (introDone && document.visibilityState === 'visible') {
        startedRef.current = true;
        try {
          sessionStorage.setItem(`${SESSION_KEY_PREFIX}${pairKey}`, 'true');
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
  }, [animate, introDone, pairKey]);

  const [barFilled, setBarFilled] = useState(animMode === 'none');
  useEffect(() => {
    if (animMode === 'none') return;
    if (animMode === 'quick') {
      const id = window.setTimeout(() => setBarFilled(true), 20);
      return () => window.clearTimeout(id);
    }
    if (!started) return;
    const id = window.setTimeout(() => setBarFilled(true), 450);
    return () => window.clearTimeout(id);
  }, [animMode, started]);

  const transitionMs = animMode === 'full' ? 1400 : animMode === 'quick' ? 300 : 0;

  return (
    <div className="glow-box border border-border-hairline bg-surface-inset rounded-lg p-5 sm:p-6 space-y-1">
      {metrics.map((m) => {
        const maxAbs = Math.max(Math.abs(m.aValue ?? 0), Math.abs(m.bValue ?? 0));
        return (
          <div key={m.key} className="comparison-metric-row">
            <div className="comparison-metric-row__label">{m.label}</div>
            <div className="comparison-metric-row__bars">
              <MetricBarRow value={m.aValue} maxAbs={maxAbs} variant="green" format={m.format} animate={animate} started={started} filled={barFilled} transitionMs={transitionMs} />
              <MetricBarRow value={m.bValue} maxAbs={maxAbs} variant="cream" format={m.format} animate={animate} started={started} filled={barFilled} transitionMs={transitionMs} />
            </div>
            <div className="comparison-metric-row__diff">
              <CountSpan value={m.diffValue} format={m.diffFormat} animate={animate} started={started} />
            </div>
          </div>
        );
      })}

      <div className="pt-3 mt-2 border-t border-border-hairline font-mono text-[13px] text-zinc-400 flex flex-wrap items-center gap-x-2 gap-y-1">
        <span className="text-zinc-300">Portfolio NAV</span>
        <span>{nameA}</span>
        <CountSpan value={navA} format={formatPaiseToRupees} animate={animate} started={started} className="text-zinc-200" />
        <span>{nameB}</span>
        <CountSpan value={navB} format={formatPaiseToRupees} animate={animate} started={started} className="text-zinc-200" />
        <span>Nifty</span>
        <CountSpan value={navNifty} format={formatPaiseToRupees} animate={animate} started={started} className="text-zinc-200" />
      </div>

      <div className="pt-3 flex items-center justify-between flex-wrap gap-2 font-mono text-xs text-zinc-400">
        <div className="flex items-center gap-5">
          <span className="inline-flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: 'var(--alloc-invested-to)' }} />
            {nameA}
          </span>
          <span className="inline-flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: 'var(--alloc-cash)' }} />
            {nameB}
          </span>
        </div>
        <span>Difference = {nameA} &minus; {nameB}</span>
      </div>
    </div>
  );
}

/** One colored, hover-spotlit name button that opens the shared agent-picker dropdown for
 * its slot. */
function SlotNameButton({
  id,
  color,
  open,
  onClick,
  btnRef,
}: {
  id: string;
  color: string;
  open: boolean;
  onClick: () => void;
  btnRef: RefObject<HTMLButtonElement | null>;
}) {
  const name = getAgentName(id);
  return (
    <button
      ref={btnRef}
      type="button"
      aria-haspopup="menu"
      aria-expanded={open}
      onClick={onClick}
      className={cn('comparison-name-btn', open && 'comparison-name-btn--open')}
      style={{
        color,
        fontFamily: "var(--font-headline), 'Red Hat Display Fallback', system-ui, sans-serif",
        fontWeight: 700,
        letterSpacing: '-0.02em',
        fontSize: 'clamp(26px, 4.5vw, 40px)',
      } as CSSProperties}
    >
      <span>{name}</span>
      <ChevronDown className={cn('w-4 h-4 flex-shrink-0 transition-transform duration-150', open && 'rotate-180')} style={{ color: '#8a8a8a' }} />
    </button>
  );
}

export default function Comparison() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [agentA, setAgentA] = useState<string>(() => {
    const p = searchParams.get('a');
    return isValidAgentId(p) ? normalizeAgentId(p) : getDefaultSlotA();
  });
  const [agentB, setAgentB] = useState<string>(() => {
    const pb = searchParams.get('b');
    if (isValidAgentId(pb)) return normalizeAgentId(pb);
    const pa = searchParams.get('a');
    const a = isValidAgentId(pa) ? normalizeAgentId(pa) : getDefaultSlotA();
    return twinIdOf(a);
  });
  const [openSlot, setOpenSlot] = useState<'a' | 'b' | null>(null);

  const [data, setData] = useState<BaselineComparison | null>(null);
  const [liveLeaderboard, setLiveLeaderboard] = useState<AgentLeaderboardEntry[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [fetchError, setFetchError] = useState<boolean>(false);
  const [isMock] = useState<boolean>(getIsMockMode());
  const [showHorizonTable, setShowHorizonTable] = useState<boolean>(false);
  const introDone = useIntroDone();

  // Keep the picks in the URL so a link opens the same comparison.
  useEffect(() => {
    setSearchParams({ a: agentA, b: agentB }, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [agentA, agentB]);

  const niftyRefLlmId = isRulesId(agentA) ? twinIdOf(agentA) : agentA;
  const isTwinPair = twinIdOf(agentA) === agentB;

  useEffect(() => {
    let isSubscribed = true;
    async function fetchComparisonData(isBackground = false) {
      if (!isBackground) {
        setLoading(true);
        setFetchError(false);
      }
      try {
        const [compData, boardData] = await Promise.all([
          apiService.getBaselineComparison(niftyRefLlmId),
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

    const pollInterval = setInterval(() => {
      fetchComparisonData(true);
    }, TELEMETRY_POLL_INTERVAL_MS);

    return () => {
      isSubscribed = false;
      clearInterval(pollInterval);
    };
  }, [niftyRefLlmId, isMock]);

  function retry() {
    setFetchError(false);
    setLoading(true);
    Promise.all([apiService.getBaselineComparison(niftyRefLlmId), apiService.getLeaderboard()])
      .then(([compData, boardData]) => {
        setData(compData);
        setLiveLeaderboard(boardData);
        setLoading(false);
      })
      .catch(() => {
        setFetchError(true);
        setLoading(false);
      });
  }

  function swap() {
    setAgentA(agentB);
    setAgentB(agentA);
  }

  function resetToTwinPair() {
    const base = baseKeyForAgentId(agentA);
    const pair = PAIR_MAP[base];
    setAgentA(pair.llmId);
    setAgentB(pair.rulesId);
  }

  function pick(slot: 'a' | 'b', id: string) {
    if (slot === 'a') {
      if (id === agentB) return;
      setAgentA(id);
    } else {
      if (id === agentA) return;
      setAgentB(id);
    }
  }

  if (fetchError) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-28 flex flex-col items-center justify-center gap-4">
        <div className="text-zinc-400 font-mono text-sm">Could not load the comparison data.</div>
        <button
          onClick={retry}
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

  const nameA = getAgentName(agentA);
  const nameB = getAgentName(agentB);
  const entryA = liveLeaderboard.find((a) => a.id === agentA);
  const entryB = liveLeaderboard.find((a) => a.id === agentB);
  const mA = metricsForAgent(entryA);
  const mB = metricsForAgent(entryB);

  const diff = (a: number | null, b: number | null) => (a != null && b != null ? a - b : null);

  const metrics: MetricConfig[] = [
    {
      key: 'return',
      label: 'Cumulative Return',
      aValue: mA.returnPct,
      bValue: mB.returnPct,
      format: fmtPctSigned,
      diffValue: diff(mA.returnPct, mB.returnPct),
      diffFormat: fmtPctSigned,
    },
    {
      key: 'maxdd',
      label: 'Max Drawdown',
      aValue: mA.maxDd,
      bValue: mB.maxDd,
      format: fmtMaxDD,
      diffValue: diff(mA.maxDd, mB.maxDd),
      diffFormat: fmtPctSigned,
    },
    {
      key: 'trades',
      label: 'Closed Trades',
      aValue: mA.trades,
      bValue: mB.trades,
      format: fmtCount,
      diffValue: diff(mA.trades, mB.trades),
      diffFormat: fmtDiffCount,
    },
    {
      key: 'winrate',
      label: 'Trade Win Rate',
      aValue: mA.winRate,
      bValue: mB.winRate,
      format: fmtWinRate,
      diffValue: diff(mA.winRate, mB.winRate),
      diffFormat: fmtPctSigned,
    },
    {
      key: 'sharpe',
      label: 'Sharpe Ratio',
      aValue: mA.sharpe,
      bValue: mB.sharpe,
      format: fmtSharpe,
      diffValue: diff(mA.sharpe, mB.sharpe),
      diffFormat: fmtDiffSharpe,
    },
  ];

  const niftyNav = data?.nifty500?.benchmarkNavPaise ?? null;

  const divergingChartData = isTwinPair
    ? data.horizonReturns.map((hr) => {
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
      })
    : [];
  const alphaSpreadPct = (mA.returnPct ?? 0) - (mB.returnPct ?? 0);
  const pairKey = `${agentA}_${agentB}`;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-7 animate-hero-entrance font-sans">

      {/* 1. HEADING: two agent pickers, swap, reset */}
      <div className="space-y-4 border-b border-border-hairline pb-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex flex-col sm:flex-row sm:items-center gap-x-3 gap-y-2 min-w-0">
            <div className="flex items-center gap-2 min-w-0">
              <AgentSwitchDropdown
                leaderboard={liveLeaderboard}
                highlightIds={[agentA]}
                disabledId={agentB}
                disabledNote="(in slot B)"
                onSelect={(id) => pick('a', id)}
                open={openSlot === 'a'}
                onOpenChange={(o) => setOpenSlot(o ? 'a' : null)}
                renderTrigger={({ ref, onClick, open }) => (
                  <SlotNameButton id={agentA} color="#13a579" open={open} onClick={onClick} btnRef={ref} />
                )}
              />
              <CategoryBadge type={isRulesId(agentA) ? 'RULES' : 'LLM'} />
            </div>

            <span className="text-zinc-500 font-mono text-sm">vs.</span>

            <div className="flex items-center gap-2 min-w-0">
              <AgentSwitchDropdown
                leaderboard={liveLeaderboard}
                highlightIds={[agentB]}
                disabledId={agentA}
                disabledNote="(in slot A)"
                onSelect={(id) => pick('b', id)}
                open={openSlot === 'b'}
                onOpenChange={(o) => setOpenSlot(o ? 'b' : null)}
                renderTrigger={({ ref, onClick, open }) => (
                  <SlotNameButton id={agentB} color="#e6dfcd" open={open} onClick={onClick} btnRef={ref} />
                )}
              />
              <CategoryBadge type={isRulesId(agentB) ? 'RULES' : 'LLM'} />
            </div>

            <button
              type="button"
              onClick={swap}
              title="Swap A and B"
              className="p-2 rounded text-zinc-400 hover:text-white hover:bg-white/[0.04] transition-colors cursor-pointer flex-shrink-0"
            >
              <ArrowLeftRight className="w-4 h-4" />
            </button>
          </div>

          <button
            type="button"
            onClick={resetToTwinPair}
            className="text-xs font-mono text-zinc-500 hover:text-brand-blue-text transition-colors cursor-pointer flex-shrink-0 text-left sm:text-right"
          >
            Reset to {getAgentName(PAIR_MAP[baseKeyForAgentId(agentA)].llmId)} vs {getAgentName(PAIR_MAP[baseKeyForAgentId(agentA)].rulesId)}
          </button>
        </div>
      </div>

      {/* 2. PAIRED METRIC BARS */}
      <PairedComparisonBody
        key={pairKey}
        pairKey={pairKey}
        nameA={nameA}
        nameB={nameB}
        metrics={metrics}
        navA={mA.nav}
        navB={mB.nav}
        navNifty={niftyNav}
        introDone={introDone}
      />

      {/* 3. NET COGNITIVE ALPHA DIVERGING BAR CHART -- only meaningful for the default twin pair */}
      {isTwinPair && (
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
      )}

      {/* 4. FOOTER AUDIT LINKS TO AGENT TERMINAL */}
      <div className="border border-border-hairline bg-surface-inset rounded-lg p-5 flex flex-col sm:flex-row items-center justify-between gap-4 font-mono text-xs">
        <div className="flex items-center gap-2.5 text-zinc-300 font-sans">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          <span>Every cited numeric indicator is audited against raw exchange snapshots in the individual Agent Terminal.</span>
        </div>
        <div className="flex items-center gap-4 flex-shrink-0">
          <Link
            to={`/portfolio/${agentA}`}
            className="text-xs font-mono text-brand-blue-text hover:underline flex items-center gap-1.5"
          >
            <span>Open {nameA} Ledger</span>
            <span>→</span>
          </Link>
          <Link
            to={`/portfolio/${agentB}`}
            className="text-xs font-mono text-brand-blue-text hover:underline flex items-center gap-1.5"
          >
            <span>Open {nameB} Ledger</span>
            <span>→</span>
          </Link>
        </div>
      </div>
    </div>
  );
}
