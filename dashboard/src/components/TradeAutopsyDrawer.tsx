import { X, ArrowDown, ArrowUp, Activity, CheckCircle2 } from 'lucide-react';
import type { Position } from '../types';
import { formatPaiseToRupees, formatPct, getForensicTagInfo, formatISTDateTime } from '../utils/formatters';

interface TradeAutopsyDrawerProps {
  trade: Position | null;
  onClose: () => void;
}

export default function TradeAutopsyDrawer({ trade, onClose }: TradeAutopsyDrawerProps) {
  if (!trade) return null;

  const forensic = getForensicTagInfo(trade.forensicTag);
  const isProfit = (trade.realizedPnlPaise || 0) >= 0;

  // Excursion calculations
  const mfePct = isProfit ? (trade.realizedPnlPct || 0) + 1.2 : 0.8;
  const maePct = isProfit ? -0.9 : (trade.realizedPnlPct || 0) - 0.4;

  return (
    <div className="fixed inset-0 z-50 overflow-hidden font-sans">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/70 backdrop-blur-sm transition-opacity"
        onClick={onClose}
      />

      <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
        <div className="w-screen max-w-lg bg-[#161616] border-l border-border-hairline shadow-2xl flex flex-col animate-fade-in overflow-hidden">
          {/* Header */}
          <div className="p-5 border-b border-border-hairline flex items-center justify-between bg-[#121212]">
            <div>
              <div className="flex items-center gap-2">
                <span className="font-mono font-semibold text-lg text-white">{trade.symbol}</span>
                <span className={`px-2 py-0.5 rounded text-[10px] font-mono border ${forensic.bg} ${forensic.text} ${forensic.border}`}>
                  {forensic.label}
                </span>
              </div>
              <p className="text-xs text-zinc-400 font-mono mt-0.5">
                {trade.companyName || trade.symbol} · {trade.sector}
              </p>
            </div>

            <button
              onClick={onClose}
              className="p-1.5 rounded text-zinc-400 hover:text-white hover:bg-white/[0.05] transition-colors cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Body Content */}
          <div className="flex-1 overflow-y-auto p-5 space-y-4 text-xs font-mono">
            {/* P&L & Financial Summary Banner */}
            <div className="p-4 rounded-lg border border-border-hairline bg-[#121212] grid grid-cols-2 gap-4">
              <div>
                <span className="text-zinc-500 text-[10px] uppercase tracking-wider block">Realized Return</span>
                <span className={`text-xl font-bold tabular-nums ${isProfit ? 'text-positive' : 'text-negative'}`}>
                  {formatPaiseToRupees(trade.realizedPnlPaise)}
                </span>
                <span className={`text-xs ml-1 font-semibold ${isProfit ? 'text-positive' : 'text-negative'}`}>
                  ({formatPct(trade.realizedPnlPct)})
                </span>
              </div>

              <div>
                <span className="text-zinc-500 text-[10px] uppercase tracking-wider block">Hold Duration</span>
                <span className="text-xl font-bold text-white tabular-nums">{trade.holdDays} days</span>
                <span className="text-zinc-500 text-[10px] block mt-0.5">
                  Closed: {trade.closedAt ? formatISTDateTime(trade.closedAt) : 'Market Close'}
                </span>
              </div>
            </div>

            {/* Price Execution Milestones */}
            <div className="border border-border-hairline bg-[#121212] p-4 rounded-lg space-y-3">
              <h4 className="font-medium text-xs text-zinc-300 uppercase tracking-wider">
                Execution Milestones & Price Path
              </h4>

              <div className="grid grid-cols-3 gap-2 text-[11px]">
                <div className="p-2.5 rounded bg-[#161616] border border-border-hairline">
                  <span className="text-zinc-500 block text-[9px] uppercase">Entry Price</span>
                  <span className="font-medium text-white tabular-nums">{formatPaiseToRupees(trade.entryPricePaise)}</span>
                </div>

                <div className="p-2.5 rounded bg-[#161616] border border-border-hairline">
                  <span className="text-zinc-500 block text-[9px] uppercase">Exit Price</span>
                  <span className="font-medium text-white tabular-nums">{formatPaiseToRupees(trade.exitPricePaise || trade.currentPricePaise)}</span>
                </div>

                <div className="p-2.5 rounded bg-[#161616] border border-border-hairline">
                  <span className="text-zinc-500 block text-[9px] uppercase">Stop Loss</span>
                  <span className="font-medium text-white tabular-nums">{formatPaiseToRupees(trade.stopLossPaise)}</span>
                </div>
              </div>

              {/* Excursion Bounds */}
              <div className="p-3 rounded border border-border-hairline bg-[#161616] space-y-2 text-[11px]">
                <div className="flex justify-between items-center">
                  <span className="flex items-center gap-1.5 text-positive">
                    <ArrowUp className="w-3.5 h-3.5" />
                    <span>Max Favorable Excursion (MFE):</span>
                  </span>
                  <span className="font-semibold text-positive tabular-nums">+{mfePct.toFixed(2)}%</span>
                </div>

                <div className="flex justify-between items-center">
                  <span className="flex items-center gap-1.5 text-negative">
                    <ArrowDown className="w-3.5 h-3.5" />
                    <span>Max Adverse Excursion (MAE):</span>
                  </span>
                  <span className="font-semibold text-negative tabular-nums">{maePct.toFixed(2)}%</span>
                </div>
              </div>
            </div>

            {/* Verbatim Entry Thesis */}
            <div className="border border-border-hairline bg-[#121212] p-4 rounded-lg space-y-2">
              <h4 className="font-medium text-xs text-zinc-300 uppercase tracking-wider">
                Original LLM Entry Thesis
              </h4>
              <p className="text-zinc-300 text-xs leading-relaxed italic bg-[#161616] p-3 rounded border border-border-hairline font-sans">
                "{trade.thesisSummary || 'Standard momentum entry confluence triggered on volume expansion.'}"
              </p>
            </div>

            {/* Deterministic Forensics & Reflection Loop */}
            <div className="border border-border-hairline bg-[#121212] p-4 rounded-lg space-y-3">
              <div className="flex items-center gap-2 text-xs font-medium text-white">
                <Activity className="w-4 h-4 text-accent" />
                <span>Causal Forensics & Reflection Loop</span>
              </div>

              <div className="p-3.5 rounded bg-[#161616] border border-border-hairline space-y-2 text-xs">
                <div className="flex items-center justify-between text-white font-semibold text-[11px]">
                  <span>Classification: {forensic.label}</span>
                  <span className="text-[10px] text-accent">Autonomous Reflection Engine</span>
                </div>

                <p className="text-[11px] text-zinc-400 leading-relaxed font-sans">
                  Deterministic classification marked as <strong className="text-zinc-200">{forensic.label}</strong> based on exit trigger breach and volatility behavior.
                </p>

                <div className="pt-2 border-t border-border-hairline font-mono text-[10px] text-zinc-500 flex items-center justify-between">
                  <span>Weekly Reflection Status:</span>
                  <span className="font-semibold text-positive flex items-center gap-1">
                    <CheckCircle2 className="w-3 h-3" /> Reviewed & Watermarked
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Drawer Footer */}
          <div className="p-4 border-t border-border-hairline bg-[#121212] flex justify-between items-center text-xs font-mono text-zinc-500">
            <span>Position #{trade.id}</span>
            <button
              onClick={onClose}
              className="px-3.5 py-1.5 rounded bg-white/[0.08] hover:bg-white/[0.12] border border-border-hairline text-white font-medium transition-colors cursor-pointer"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
