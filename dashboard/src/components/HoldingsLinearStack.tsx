import type { Position } from '../types';
import { formatPaiseToRupees, formatPct } from '../utils/formatters';
import { cn } from '../utils/cn';

interface HoldingsLinearStackProps {
  positions: Position[];
  cashPaise: number;
  totalNavPaise: number;
  pendingCount?: number;
}

export default function HoldingsLinearStack({
  positions,
  totalNavPaise,
  pendingCount = 0,
}: HoldingsLinearStackProps) {
  const activePositions = positions.filter((p) => p.status === 'OPEN');
  const effectiveNav = totalNavPaise > 0 ? totalNavPaise : 50000000;

  return (
    <div className="bg-[#161616] border border-border-hairline p-5 rounded-lg font-sans h-full flex flex-col justify-between">
      <div>
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border-hairline pb-3 mb-2 font-mono text-xs">
          <div className="flex items-center gap-2">
            <h3 className="font-serif text-lg font-medium text-white tracking-tight">
              Holdings
            </h3>
            <span className="px-2 py-0.5 rounded bg-white/[0.04] text-zinc-300 border border-border-hairline text-[11px]">
              {activePositions.length} {activePositions.length === 1 ? 'Asset' : 'Assets'}
            </span>
          </div>

          <div className="flex items-center gap-1.5 text-[11px] text-zinc-400 font-mono">
            <span className="w-1.5 h-1.5 rounded-full bg-positive animate-pulse" />
            <span>Intraday LTP</span>
          </div>
        </div>

        {/* Linear Stack of Holdings */}
        <div className="divide-y divide-border-hairline">
          {activePositions.length === 0 ? (
            <div className="py-8 text-center space-y-2.5 font-mono">
              <div className="text-zinc-400 text-xs">
                No active stock positions. Portfolio is 100% in liquid cash reserve.
              </div>
              {pendingCount > 0 ? (
                <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded bg-amber-500/10 border border-amber-500/25 text-amber-300 text-[11px]">
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
                  <span>{pendingCount} order{pendingCount > 1 ? 's' : ''} queued for execution at 09:15 IST</span>
                </div>
              ) : null}
            </div>
          ) : (
            activePositions.map((pos) => {
              const currentValuePaise = pos.quantity * pos.currentPricePaise;
              const weightPct = (currentValuePaise / effectiveNav) * 100;
              const isProfit = pos.unrealizedPnlPaise >= 0;

              // Distance to stop-loss
              const stopLossPaise = pos.stopLossPaise;
              const stopDistancePct =
                pos.currentPricePaise > 0 && stopLossPaise > 0
                  ? ((stopLossPaise - pos.currentPricePaise) / pos.currentPricePaise) * 100
                  : null;

              return (
                <div
                  key={pos.symbol}
                  className="py-3 px-1 flex items-center justify-between gap-4 hover:bg-white/[0.02] transition-colors rounded group font-mono text-xs"
                >
                  {/* Left Side: Stock Symbol, Allocation Pill & Position Sizing */}
                  <div className="space-y-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-white text-sm tracking-tight font-mono">
                        {pos.symbol}
                      </span>
                      <span className="text-[10px] px-1.5 py-0.2 rounded bg-white/5 text-zinc-400 border border-border-hairline">
                        {weightPct.toFixed(1)}%
                      </span>
                    </div>

                    <div className="text-[11px] text-zinc-400 flex flex-wrap items-center gap-x-2 gap-y-0.5">
                      <span>{pos.quantity} shares @ {formatPaiseToRupees(pos.entryPricePaise)}</span>
                      {stopDistancePct !== null && (
                        <>
                          <span className="text-zinc-600">·</span>
                          <span className="text-zinc-500">
                            Stop: {formatPaiseToRupees(stopLossPaise)} ({stopDistancePct.toFixed(1)}%)
                          </span>
                        </>
                      )}
                    </div>
                  </div>

                  {/* Right Side: Current Value, LTP & Unrealized PnL */}
                  <div className="text-right space-y-0.5">
                    <div className="font-semibold text-white text-sm tabular-nums">
                      {formatPaiseToRupees(currentValuePaise)}
                    </div>
                    <div className="text-[11px] text-zinc-400">
                      LTP: <span className="text-zinc-200">{formatPaiseToRupees(pos.currentPricePaise)}</span>
                    </div>
                    <div
                      className={cn(
                        "text-xs font-medium tabular-nums",
                        isProfit ? "text-positive" : "text-negative"
                      )}
                    >
                      {isProfit ? '+' : ''}{formatPaiseToRupees(pos.unrealizedPnlPaise)}{' '}
                      <span className="text-[10px] opacity-90">
                        ({formatPct(pos.unrealizedPnlPct)})
                      </span>
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
