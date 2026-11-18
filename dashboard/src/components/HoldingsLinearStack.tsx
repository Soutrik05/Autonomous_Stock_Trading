import { useEffect, useState } from 'react';
import type { Position } from '../types';
import { formatPaiseToRupees, formatPct } from '../utils/formatters';
import { cn } from '../utils/cn';
import { useCountUp } from '../hooks/useCountUp';
import { usePrefersReducedMotion } from '../hooks/usePrefersReducedMotion';

interface HoldingsLinearStackProps {
  agentId: string;
  introDone: boolean;
  positions: Position[];
  startingCapitalPaise: number;
  totalNavPaise: number;
  totalReturnPct: number;
  dayChangePaise?: number;
  dayChangePct?: number;
  pendingCount?: number;
}

const SESSION_KEY_PREFIX = 'stockminds_terminal_count_';
const COUNT_OPTS = { duration: 1300, delay: 250 };

/** Decided once per mount (the parent remounts this component with key={agentId} on agent
 * switch) -- true only the first time this agent's Holdings tab is opened this browser
 * session. Never written anywhere except this one check-and-mark. */
function decideFirstOpen(agentId: string): boolean {
  const key = `${SESSION_KEY_PREFIX}${agentId}`;
  try {
    if (sessionStorage.getItem(key) === 'true') return false;
    sessionStorage.setItem(key, 'true');
    return true;
  } catch {
    return false;
  }
}

const formatUnsignedPaise = (n: number) => formatPaiseToRupees(Math.round(n));
const formatSignedPaise = (n: number) => `${n >= 0 ? '+' : ''}${formatPaiseToRupees(Math.round(n))}`;
const formatUnsignedPct1 = (n: number) => `${n.toFixed(1)}%`;

/**
 * Clean, brokerage-grade Holdings view (Option A 3-Column Layout).
 *
 * Header:
 * - LHS: Current Valuation of active holdings (color-coded green/red), Total Invested (pure white),
 *        Net Return difference in Rupees & %, and 1D Change.
 * - RHS: Available / uninvested capital waiting to be deployed, along with % of seed capital.
 *        Font sizes, hierarchy, and weights are identically balanced across LHS and RHS.
 * - Below: a full-width Invested/Cash allocation bar + legend.
 *
 * Rows:
 * - LHS: Position identity, allocation weight, and cost basis.
 * - Center: Live LTP & Intraday 1D change.
 * - RHS: Current mark-to-market valuation, net return in Rupees & %, and invested cost basis.
 *
 * The header's money figures count up from 0 once, the first time this agent's Holdings tab
 * is opened in this browser session (see decideFirstOpen), using the shared useCountUp hook --
 * never on a later visit, never on a background data refresh, and never under
 * prefers-reduced-motion. If the intro overlay is still showing when this mounts, the count
 * waits for it (gated on `introDone`) rather than running invisibly underneath it.
 */
export default function HoldingsLinearStack({
  agentId,
  introDone,
  positions,
  startingCapitalPaise,
  totalNavPaise,
  dayChangePaise,
  dayChangePct,
  pendingCount = 0,
}: HoldingsLinearStackProps) {
  const [isFirstOpen] = useState(() => decideFirstOpen(agentId));
  const reducedMotion = usePrefersReducedMotion();
  const playCountUp = isFirstOpen && !reducedMotion;
  const barAnimating = playCountUp && introDone;

  const activePositions = positions.filter((p) => p.status === 'OPEN');
  const effectiveNav = totalNavPaise > 0 ? totalNavPaise : 50000000;
  const seedCapital = startingCapitalPaise > 0 ? startingCapitalPaise : 50000000;

  // Invested capital across active stock positions
  const totalInvestedPaise = activePositions.reduce(
    (sum, pos) => sum + pos.quantity * pos.entryPricePaise,
    0
  );

  // Current market valuation of active stock positions
  const currentInvestedValuationPaise = activePositions.reduce(
    (sum, pos) => sum + pos.quantity * pos.currentPricePaise,
    0
  );

  // Returns strictly on deployed capital
  const deployedReturnPaise = currentInvestedValuationPaise - totalInvestedPaise;
  const deployedReturnPct = totalInvestedPaise > 0
    ? (deployedReturnPaise / totalInvestedPaise) * 100
    : 0;
  const isProfit = deployedReturnPaise >= 0;

  // Available cash waiting to be deployed
  const availableCashPaise = Math.max(0, effectiveNav - currentInvestedValuationPaise);
  const availableCashPctOfSeed = seedCapital > 0
    ? (availableCashPaise / seedCapital) * 100
    : 0;
  const investedPctOfSeed = seedCapital > 0
    ? (totalInvestedPaise / seedCapital) * 100
    : 0;

  // Intraday 1D price change on active holdings
  const activeDayChangePaise = activePositions.reduce((sum, pos) => {
    if (pos.dayChangePaise !== undefined) {
      return sum + (pos.quantity * pos.dayChangePaise);
    }
    const dayPct = pos.dayChangePct ?? 0;
    return sum + Math.round(pos.quantity * pos.currentPricePaise * (dayPct / 100));
  }, 0);

  const effectiveDayChangePaise = activePositions.length > 0
    ? activeDayChangePaise
    : (dayChangePaise ?? 0);
  const prevInvestedValuationPaise = currentInvestedValuationPaise - effectiveDayChangePaise;
  const effectiveDayChangePct = activePositions.length > 0
    ? (prevInvestedValuationPaise > 0
        ? (effectiveDayChangePaise / prevInvestedValuationPaise) * 100
        : (currentInvestedValuationPaise > 0 ? (effectiveDayChangePaise / currentInvestedValuationPaise) * 100 : 0))
    : (dayChangePct ?? 0);
  const isDayProfit = effectiveDayChangePaise >= 0;

  // Gate the value fed to useCountUp on introDone (while playing): shows "-" behind the
  // (opaque, full-screen) intro overlay instead of starting the count underneath it, then
  // becomes the first real value -- and so starts the one-shot count -- once introDone flips
  // true. When not playing (repeat visit / reduced motion), feed the real value from the
  // start and simply ignore the hook's own (still-animating-in-background) text below.
  const gate = (target: number) => (playCountUp ? (introDone ? target : undefined) : target);

  const investedHook = useCountUp(gate(totalInvestedPaise), formatUnsignedPaise, COUNT_OPTS);
  const currentValuationHook = useCountUp(gate(currentInvestedValuationPaise), formatUnsignedPaise, COUNT_OPTS);
  const deployedReturnPaiseHook = useCountUp(gate(deployedReturnPaise), formatSignedPaise, COUNT_OPTS);
  const deployedReturnPctHook = useCountUp(gate(deployedReturnPct), formatPct, COUNT_OPTS);
  const dayChangePaiseHook = useCountUp(gate(effectiveDayChangePaise), formatSignedPaise, COUNT_OPTS);
  const dayChangePctHook = useCountUp(gate(effectiveDayChangePct), formatPct, COUNT_OPTS);
  const cashHook = useCountUp(gate(availableCashPaise), formatUnsignedPaise, COUNT_OPTS);
  const investedPctHook = useCountUp(gate(investedPctOfSeed), formatUnsignedPct1, COUNT_OPTS);
  const cashPctHook = useCountUp(gate(availableCashPctOfSeed), formatUnsignedPct1, COUNT_OPTS);

  const investedDisplay = playCountUp ? investedHook : formatUnsignedPaise(totalInvestedPaise);
  const currentValuationDisplay = playCountUp ? currentValuationHook : formatUnsignedPaise(currentInvestedValuationPaise);
  const deployedReturnPaiseDisplay = playCountUp ? deployedReturnPaiseHook : formatSignedPaise(deployedReturnPaise);
  const deployedReturnPctDisplay = playCountUp ? deployedReturnPctHook : formatPct(deployedReturnPct);
  const dayChangePaiseDisplay = playCountUp ? dayChangePaiseHook : formatSignedPaise(effectiveDayChangePaise);
  const dayChangePctDisplay = playCountUp ? dayChangePctHook : formatPct(effectiveDayChangePct);
  const cashDisplay = playCountUp ? cashHook : formatUnsignedPaise(availableCashPaise);
  const investedPctDisplay = playCountUp ? investedPctHook : formatUnsignedPct1(investedPctOfSeed);
  const cashPctDisplay = playCountUp ? cashPctHook : formatUnsignedPct1(availableCashPctOfSeed);

  // Allocation bar fill: transform scaleX from 0 -> 1, starting 0.45s after introDone, once.
  // The lazy initial state already reflects whether we're animating at all (no sync setState
  // needed for that); the effect only schedules the one-shot delayed fill when we are.
  const [barFilled, setBarFilled] = useState(!playCountUp);
  useEffect(() => {
    if (!barAnimating) return;
    const id = window.setTimeout(() => setBarFilled(true), 450);
    return () => window.clearTimeout(id);
  }, [barAnimating]);

  const investedBarPct = Math.max(0, Math.min(100, investedPctOfSeed));
  const cashBarPct = Math.max(0, Math.min(100, availableCashPctOfSeed));

  return (
    <div className="glow-box rounded-lg">
    <div className="bg-[#161616] border border-border-hairline rounded-lg font-sans overflow-hidden">
      {/* 1. Header: Balanced LHS (Deployed Capital) vs RHS (Available Capital) */}
      <div className="p-4 sm:p-5 border-b border-border-hairline space-y-4 font-mono">
        {/* Title bar */}
        <div className="flex items-center justify-between gap-2 text-xs">
          <div className="flex items-center gap-2">
            <h3 className="font-sans text-lg font-semibold text-white tracking-tight">
              Holdings
            </h3>
            <span className="px-2 py-0.5 rounded bg-white/[0.04] text-zinc-300 border border-border-hairline text-[11px]">
              {activePositions.length} {activePositions.length === 1 ? 'Asset' : 'Assets'}
            </span>
          </div>
        </div>

        {/* Primary Data Row: LHS Deployed vs RHS Available (Identical font size, weight, and visual hierarchy) */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-1">
          {/* LHS: Current Valuation & Returns on Deployed Capital */}
          <div className="space-y-1.5">
            <div className="text-[12px] text-zinc-400 font-sans flex items-center gap-1.5 flex-wrap">
              <span className="text-zinc-500 font-mono text-[12px]">Invested:</span>
              <strong
                className="font-mono text-[24px] font-semibold tabular-nums"
                style={{ color: '#10b981' }}
              >
                {investedDisplay}
              </strong>
              <span className="text-zinc-500 font-mono text-[12px]">({investedPctDisplay} of seed)</span>
            </div>

            {/* Current Value +/- Net Returns on Invested */}
            <div className="flex items-baseline gap-2.5 flex-wrap">
              <span className="text-zinc-500 font-mono text-[12px]">Current:</span>
              <span
                className={cn(
                  "text-[34px] font-bold font-mono tabular-nums leading-none",
                  isProfit ? "text-positive" : "text-negative"
                )}
              >
                {currentValuationDisplay}
              </span>
              <span
                className={cn(
                  "text-sm sm:text-base font-semibold font-mono tabular-nums",
                  isProfit ? "text-positive" : "text-negative"
                )}
              >
                {deployedReturnPaiseDisplay} ({deployedReturnPctDisplay})
              </span>
            </div>

            {/* 1D Change on Holdings */}
            <div className="flex items-center gap-1.5 text-[12px] font-mono">
              <span className="text-zinc-500 font-sans">1D Change:</span>
              <span
                className={cn(
                  "font-semibold tabular-nums",
                  isDayProfit ? "text-positive" : "text-negative"
                )}
              >
                {dayChangePaiseDisplay} ({dayChangePctDisplay})
              </span>
            </div>
          </div>

          {/* RHS: Available Capital Waiting to be Deployed (Identical typography structure) */}
          <div className="space-y-1.5 md:text-right flex flex-col md:items-end justify-start">
            <span className="text-zinc-500 font-mono text-[12px]">Cash Available</span>
            <div className="flex items-baseline md:justify-end gap-2.5 flex-wrap">
              <span
                className="text-[34px] font-mono font-bold tabular-nums leading-none"
                style={{ color: '#4F8FE0' }}
              >
                {cashDisplay}
              </span>
            </div>
            <span className="text-zinc-400 font-mono text-[12px]">({cashPctDisplay})</span>
          </div>
        </div>

        {/* Allocation bar: Invested (green) vs Cash (blue) segments, real % of seed capital */}
        <div className="pt-1 space-y-2">
          <div className="w-full h-4 rounded-full bg-[#222] flex gap-[3px] overflow-hidden">
            <div
              className="h-full rounded-full"
              style={{
                width: `${investedBarPct}%`,
                backgroundColor: '#10b981',
                transform: barFilled ? 'scaleX(1)' : 'scaleX(0)',
                transformOrigin: 'left',
                transition: barAnimating ? 'transform 1.4s cubic-bezier(0.22, 1, 0.36, 1)' : 'none',
              }}
            />
            <div
              className="h-full rounded-full"
              style={{
                width: `${cashBarPct}%`,
                backgroundColor: '#2f6fc0',
                transform: barFilled ? 'scaleX(1)' : 'scaleX(0)',
                transformOrigin: 'left',
                transition: barAnimating ? 'transform 1.4s cubic-bezier(0.22, 1, 0.36, 1)' : 'none',
              }}
            />
          </div>
          <div className="flex items-center justify-between text-[11px] font-mono text-zinc-400 flex-wrap gap-y-1">
            <span className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full inline-block" style={{ backgroundColor: '#10b981' }} />
              Invested {investedPctOfSeed.toFixed(1)}% · {activePositions.length} {activePositions.length === 1 ? 'stock' : 'stocks'}
            </span>
            <span className="text-zinc-500">Starting money {formatPaiseToRupees(seedCapital)}</span>
            <span className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full inline-block" style={{ backgroundColor: '#2f6fc0' }} />
              Cash {availableCashPctOfSeed.toFixed(1)}% · ready to use
            </span>
          </div>
        </div>
      </div>

      {/* 2. Linear Stack of Holdings (Option A 3-Column Layout) */}
      <div className="divide-y divide-border-hairline">
        {activePositions.length === 0 ? (
          <div className="py-10 text-center space-y-2.5 font-mono">
            <div className="text-zinc-400 text-[14px]">
              No active stock positions. 100% in liquid capital.
            </div>
            {pendingCount > 0 && (
              <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded bg-amber-500/10 border border-amber-500/25 text-amber-300 text-[12px]">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
                <span>{pendingCount} order{pendingCount > 1 ? 's' : ''} queued for 09:15 IST</span>
              </div>
            )}
          </div>
        ) : (
          activePositions.map((pos) => {
            const currentValuePaise = pos.quantity * pos.currentPricePaise;
            const investedPaise = pos.quantity * pos.entryPricePaise;
            const weightPct = effectiveNav > 0 ? (currentValuePaise / effectiveNav) * 100 : 0;
            const isProfit = pos.unrealizedPnlPaise >= 0;

            const dayPct = pos.dayChangePct ?? 0;
            const dayDiffPaise = pos.dayChangePaise !== undefined
              ? pos.dayChangePaise
              : (pos.currentPricePaise > 0 && dayPct !== 0 ? Math.round(pos.currentPricePaise * (dayPct / 100)) : 0);
            const isDayProfit = (pos.dayChangePaise !== undefined ? pos.dayChangePaise : dayPct) >= 0;

            const stopLossPaise = pos.stopLossPaise;
            const stopDistancePct =
              pos.currentPricePaise > 0 && stopLossPaise > 0
                ? ((stopLossPaise - pos.currentPricePaise) / pos.currentPricePaise) * 100
                : null;

            return (
              <div
                key={pos.symbol}
                className="py-3.5 px-4 sm:px-5 grid grid-cols-1 md:grid-cols-12 gap-3 md:gap-4 items-center hover:bg-white/[0.02] transition-colors group font-mono text-[14px]"
              >
                {/* 1. LHS: Symbol, Weight, Company & Shares @ Entry (col-span-5) */}
                <div className="md:col-span-5 space-y-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-bold text-white text-[15px] sm:text-base tracking-tight font-mono">
                      {pos.symbol}
                    </span>
                    <span className="text-[11px] px-1.5 py-0.5 rounded bg-white/5 text-zinc-300 border border-border-hairline font-mono">
                      {weightPct.toFixed(1)}%
                    </span>
                    {pos.companyName && (
                      <span className="text-zinc-400 text-[13px] font-sans truncate max-w-[150px] sm:max-w-[200px]">
                        {pos.companyName}
                      </span>
                    )}
                  </div>

                  <div className="text-[12px] text-zinc-400 flex flex-wrap items-center gap-x-2 gap-y-0.5 font-mono">
                    <span>{pos.quantity} shares @ Avg {formatPaiseToRupees(pos.entryPricePaise)}</span>
                    {stopDistancePct !== null && (
                      <>
                        <span className="text-zinc-600">·</span>
                        <span className="text-zinc-500">
                          Stop {formatPaiseToRupees(stopLossPaise)} ({stopDistancePct.toFixed(1)}%)
                        </span>
                      </>
                    )}
                  </div>
                </div>

                {/* 2. Center Column: LTP & 1D Move (col-span-3 text-left md:text-center) */}
                <div className="md:col-span-3 space-y-0.5 font-mono">
                  <div className="flex items-baseline md:justify-center gap-1.5">
                    <span className="text-[11px] text-zinc-500 font-sans">LTP</span>
                    <span className="text-[14px] sm:text-[15px] font-bold text-white tabular-nums">
                      {formatPaiseToRupees(pos.currentPricePaise)}
                    </span>
                  </div>
                  <div className="flex items-baseline md:justify-center gap-1 text-[12px]">
                    <span className="text-[11px] text-zinc-500 font-sans">1D</span>
                    <span
                      className={cn(
                        "font-semibold tabular-nums",
                        isDayProfit ? "text-positive" : "text-negative"
                      )}
                    >
                      {isDayProfit ? '+' : ''}{formatPaiseToRupees(dayDiffPaise)} ({formatPct(dayPct)})
                    </span>
                  </div>
                </div>

                {/* 3. RHS: Current Value (+/- %) on Line 1, Total Invested on Line 2 (col-span-4 text-left md:text-right) */}
                <div className="md:col-span-4 space-y-0.5 font-mono md:text-right">
                  {/* Line 1: Current Value + Net Return diff in Rupees & % */}
                  <div className="flex items-baseline md:justify-end gap-1.5 flex-wrap">
                    <span className="font-bold text-white text-[14px] sm:text-[15px] tabular-nums">
                      {formatPaiseToRupees(currentValuePaise)}
                    </span>
                    <span
                      className={cn(
                        "text-[12px] sm:text-[13px] font-semibold tabular-nums",
                        isProfit ? "text-positive" : "text-negative"
                      )}
                    >
                      {isProfit ? '+' : ''}{formatPaiseToRupees(pos.unrealizedPnlPaise)} ({formatPct(pos.unrealizedPnlPct)})
                    </span>
                  </div>

                  {/* Line 2: Total Invested Outlay (zero labels) */}
                  <div className="text-[12px] text-zinc-400 tabular-nums">
                    {formatPaiseToRupees(investedPaise)}
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
    </div>
  );
}
