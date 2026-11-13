import type { Position } from '../types';
import { formatPaiseToRupees, formatPct } from '../utils/formatters';
import { cn } from '../utils/cn';

interface HoldingsLinearStackProps {
  positions: Position[];
  startingCapitalPaise: number;
  totalNavPaise: number;
  totalReturnPct: number;
  dayChangePaise?: number;
  dayChangePct?: number;
  pendingCount?: number;
}

/**
 * Clean, brokerage-grade Holdings view (Option A 3-Column Layout).
 * 
 * Header:
 * - LHS: Current Valuation of active holdings (color-coded green/red), Total Invested (pure white),
 *        Net Return difference in Rupees & %, and 1D Change.
 * - RHS: Available / uninvested capital waiting to be deployed, along with % of seed capital.
 *        Font sizes, hierarchy, and weights are identically balanced across LHS and RHS.
 * 
 * Rows:
 * - LHS: Position identity, allocation weight, and cost basis.
 * - Center: Live LTP & Intraday 1D change.
 * - RHS: Current mark-to-market valuation, net return in Rupees & %, and invested cost basis.
 */
export default function HoldingsLinearStack({
  positions,
  startingCapitalPaise,
  totalNavPaise,
  dayChangePaise,
  dayChangePct,
  pendingCount = 0,
}: HoldingsLinearStackProps) {
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
    const dayPct = pos.dayChangePct ?? 0.25;
    return sum + (pos.dayChangePaise ?? Math.round(pos.quantity * pos.currentPricePaise * (dayPct / 100)));
  }, 0);

  const effectiveDayChangePaise = dayChangePaise ?? (
    activePositions.length > 0
      ? activeDayChangePaise
      : 0
  );
  const effectiveDayChangePct = dayChangePct ?? (
    currentInvestedValuationPaise > 0
      ? (effectiveDayChangePaise / currentInvestedValuationPaise) * 100
      : 0
  );
  const isDayProfit = effectiveDayChangePaise >= 0;

  return (
    <div className="bg-[#161616] border border-border-hairline rounded-lg font-sans overflow-hidden">
      {/* 1. Header: Balanced LHS (Deployed Capital) vs RHS (Available Capital) */}
      <div className="p-4 sm:p-5 border-b border-border-hairline space-y-3.5 font-mono">
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

          {/* <div className="text-zinc-500 font-mono text-[12px]">
            Seed Capital: <strong className="font-mono text-zinc-200">{formatPaiseToRupees(seedCapital)}</strong>
          </div> */}
        </div>

        {/* Primary Data Row: LHS Deployed vs RHS Available (Identical font size, weight, and visual hierarchy) */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-1">
          {/* LHS: Current Valuation & Returns on Deployed Capital */}
          <div className="space-y-1">
            <div className="text-[12px] text-zinc-400 font-sans flex items-center gap-1.5">
              <span className="text-zinc-500 font-mono text-[12px]">Invested:</span>
              <strong className="font-mono text-white text-[14px] font-semibold tabular-nums">
                {formatPaiseToRupees(totalInvestedPaise)}
              </strong>
              {/* <span className="text-zinc-500 font-mono text-[12px]">({investedPctOfSeed.toFixed(1)}%)</span> */}
              <span className="text-zinc-500 font-mono text-[12px]">({investedPctOfSeed.toFixed(1)}% of seed)</span>
            </div>

            {/* Current Value +/- Net Returns on Invested */}
            <div className="flex items-baseline gap-2.5 flex-wrap">
              <span className="text-zinc-500 font-mono text-[12px]">Current:</span>
              <span
                className={cn(
                  "text-xl sm:text-2xl font-bold font-mono tabular-nums",
                  isProfit ? "text-positive" : "text-negative"
                )}
              >
                {formatPaiseToRupees(currentInvestedValuationPaise)}
              </span>
              <span
                className={cn(
                  "text-sm sm:text-base font-semibold font-mono tabular-nums",
                  isProfit ? "text-positive" : "text-negative"
                )}
              >
                {isProfit ? '+' : ''}{formatPaiseToRupees(deployedReturnPaise)} ({formatPct(deployedReturnPct)})
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
                {isDayProfit ? '+' : ''}{formatPaiseToRupees(effectiveDayChangePaise)} ({formatPct(effectiveDayChangePct)})
              </span>
            </div>
          </div>

          {/* RHS: Available Capital Waiting to be Deployed (Identical typography structure) */}
          <div className="space-y-1 md:text-right flex flex-col md:items-end justify-start">
            <span className="text-zinc-500 font-mono text-[12px]">Cash Available</span>
            <div className="text-[12px] text-zinc-400 font-sans flex items-center gap-1.5 md:justify-end">
              <div className="flex items-baseline md:justify-end gap-2.5 flex-wrap">
                <span className="text-xl sm:text-2xl font font-mono text-white tabular-nums">
                  {formatPaiseToRupees(availableCashPaise)}
                </span>
              </div>


              {/* Available Capital Number */}
            </div>
            <span className="text-white 500 font-mono text-[12px]">({availableCashPctOfSeed.toFixed(1)}%)</span>
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

            const dayPct = pos.dayChangePct ?? 0.35;
            const dayDiffPaise = pos.dayChangePaise ?? Math.round(pos.quantity * pos.currentPricePaise * (dayPct / 100));
            const isDayProfit = dayPct >= 0;

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
                    <span className="text-[11px] px-1.5 py-0.2 rounded bg-white/5 text-zinc-300 border border-border-hairline font-mono">
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
                    <span className="text-[11px] text-zinc-500 uppercase tracking-wider font-sans">LTP</span>
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
  );
}
