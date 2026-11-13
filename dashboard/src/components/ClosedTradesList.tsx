import { useState } from 'react';
import type { Position } from '../types';
import { formatPaiseToRupees, formatPct, getForensicTagInfo } from '../utils/formatters';
import { cn } from '../utils/cn';
import TradeAutopsyDrawer from './TradeAutopsyDrawer';

interface ClosedTradesListProps {
  positions: Position[];
}

export default function ClosedTradesList({ positions }: ClosedTradesListProps) {
  const [autopsyTrade, setAutopsyTrade] = useState<Position | null>(null);
  const closedPositions = positions.filter((p) => p.status === 'CLOSED');

  return (
    <div className="bg-[#161616] border border-border-hairline rounded-lg font-sans overflow-hidden">
      {/* Header */}
      <div className="p-4 sm:p-5 border-b border-border-hairline flex items-center justify-between font-mono text-xs">
        <div className="flex items-center gap-2">
          <h3 className="font-serif text-lg font-medium text-white tracking-tight">
            Past Closed Trades
          </h3>
          <span className="px-2 py-0.5 rounded bg-white/[0.04] text-zinc-300 border border-border-hairline text-[11px]">
            {closedPositions.length} {closedPositions.length === 1 ? 'Trade' : 'Trades'}
          </span>
        </div>

        <span className="text-[11px] text-zinc-500 font-mono">
          Settled Exits
        </span>
      </div>

      {/* Hairline Linear List */}
      <div className="divide-y divide-border-hairline">
        {closedPositions.length === 0 ? (
          <div className="py-10 text-center font-mono text-xs text-zinc-400">
            No closed trades yet. Settled exits and trade autopsies will appear here.
          </div>
        ) : (
          closedPositions.map((pos) => {
            const isProfit = (pos.realizedPnlPaise || 0) >= 0;
            const forensic = getForensicTagInfo(pos.forensicTag);

            return (
              <div
                key={pos.id}
                className="py-3.5 px-4 sm:px-5 flex items-center justify-between gap-4 hover:bg-white/[0.02] transition-colors group font-mono text-xs"
              >
                {/* Left: Ticker, Company, Forensic Badge, Trade Bounds */}
                <div className="space-y-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-bold text-white text-sm sm:text-base tracking-tight font-mono">
                      {pos.symbol}
                    </span>
                    {pos.companyName && (
                      <span className="text-zinc-400 text-xs font-sans truncate max-w-[160px] sm:max-w-[280px]">
                        {pos.companyName}
                      </span>
                    )}
                    {pos.forensicTag && pos.forensicTag !== 'NONE' && (
                      <span className={cn("px-1.5 py-0.2 rounded text-[10px] font-mono border", forensic.bg, forensic.text, forensic.border)}>
                        {forensic.label}
                      </span>
                    )}
                  </div>

                  <div className="text-[11px] text-zinc-400 flex flex-wrap items-center gap-x-2 gap-y-0.5 font-mono">
                    <span>{pos.quantity} shares</span>
                    <span className="text-zinc-600">·</span>
                    <span>Entry {formatPaiseToRupees(pos.entryPricePaise)}</span>
                    <span className="text-zinc-600">→</span>
                    <span>Exit {formatPaiseToRupees(pos.exitPricePaise || pos.currentPricePaise)}</span>
                    <span className="text-zinc-600">·</span>
                    <span>{pos.holdDays}d hold</span>
                  </div>
                </div>

                {/* Right: Realized P&L & Autopsy Button */}
                <div className="flex items-center gap-4 text-right font-mono flex-shrink-0">
                  <div className="space-y-0.5">
                    <div
                      className={cn(
                        "text-sm sm:text-base font-bold tabular-nums",
                        isProfit ? "text-positive" : "text-negative"
                      )}
                    >
                      {isProfit ? '+' : ''}{formatPaiseToRupees(pos.realizedPnlPaise || 0)}
                    </div>
                    <div
                      className={cn(
                        "text-xs font-semibold tabular-nums",
                        isProfit ? "text-positive/90" : "text-negative/90"
                      )}
                    >
                      {formatPct(pos.realizedPnlPct || 0)}
                    </div>
                  </div>

                  <button
                    onClick={() => setAutopsyTrade(pos)}
                    className="px-2.5 py-1.5 rounded bg-white/[0.04] hover:bg-white/[0.08] text-zinc-300 hover:text-white border border-border-hairline text-xs font-mono transition-colors cursor-pointer"
                  >
                    Autopsy ↗
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Trade Autopsy Modal Drawer */}
      {autopsyTrade && (
        <TradeAutopsyDrawer
          trade={autopsyTrade}
          onClose={() => setAutopsyTrade(null)}
        />
      )}
    </div>
  );
}
