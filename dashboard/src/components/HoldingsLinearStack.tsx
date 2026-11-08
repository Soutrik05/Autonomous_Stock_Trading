import type { Position } from '../types';
import { formatPaiseToRupees, formatPct } from '../utils/formatters';

interface HoldingsLinearStackProps {
  positions: Position[];
  cashPaise: number;
  totalNavPaise: number;
}

export default function HoldingsLinearStack({
  positions,
  totalNavPaise,
}: HoldingsLinearStackProps) {
  const activePositions = positions.filter((p) => p.status === 'OPEN');
  const effectiveNav = totalNavPaise > 0 ? totalNavPaise : 10000000;

  return (
    <div className="bg-white/[0.02] border border-white/[0.08] p-5 rounded-sm font-sans h-full flex flex-col justify-between">
      <div>
        {/* Header (Minimal, Monograph style: Title & Count only, No Subtitle) */}
        <div className="flex items-center justify-between border-b border-white/[0.08] pb-3 mb-2">
          <h3 className="font-display text-lg font-medium text-white tracking-tight">
            Holdings
          </h3>
          <span className="text-xs font-mono px-2 py-0.5 rounded bg-white/[0.04] text-zinc-300 border border-white/10">
            {activePositions.length} {activePositions.length === 1 ? 'Asset' : 'Assets'}
          </span>
        </div>

        {/* Linear Stack of Holdings (Stock on Left, Amount & PnL on Right) */}
        <div className="divide-y divide-white/[0.06]">
          {activePositions.length === 0 ? (
            <div className="py-10 text-center text-zinc-500 font-mono text-xs">
              No active stock positions. Portfolio is 100% in liquid cash reserve.
            </div>
          ) : (
            activePositions.map((pos) => {
              const currentValuePaise = pos.quantity * pos.currentPricePaise;
              const weightPct = (currentValuePaise / effectiveNav) * 100;
              const isProfit = pos.unrealizedPnlPaise >= 0;

              return (
                <div
                  key={pos.symbol}
                  className="py-3 px-1.5 flex items-center justify-between gap-4 hover:bg-white/[0.02] transition-colors rounded-sm group"
                >
                  {/* Left Side: Stock Symbol, Allocation Pill & Position Sizing */}
                  <div className="space-y-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-white text-[15px] tracking-tight font-mono">
                        {pos.symbol}
                      </span>
                      <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-white/5 text-zinc-400 border border-white/10">
                        {weightPct.toFixed(1)}%
                      </span>
                    </div>
                    <p className="text-xs text-zinc-400 font-mono truncate">
                      {pos.quantity} shares <span className="text-zinc-600">·</span> Avg. {formatPaiseToRupees(pos.entryPricePaise)}
                    </p>
                  </div>

                  {/* Right Side: Investment Valuation & Profit / Loss */}
                  <div className="text-right space-y-1 font-mono">
                    <div className="font-semibold text-white text-sm tabular-nums">
                      {formatPaiseToRupees(currentValuePaise)}
                    </div>
                    <div
                      className={`text-xs font-medium tabular-nums ${
                        isProfit ? 'text-emerald-400' : 'text-[#c4553f]'
                      }`}
                    >
                      {isProfit ? '+' : ''}{formatPaiseToRupees(pos.unrealizedPnlPaise)}{' '}
                      <span className="text-[11px] opacity-90">
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
