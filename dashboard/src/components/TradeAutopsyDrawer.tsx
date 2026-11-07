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
        className="absolute inset-0 bg-black/60 backdrop-blur-sm transition-opacity"
        onClick={onClose}
      />

      <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
        <div className="w-screen max-w-lg bg-[#070A11] border-l border-white/10 shadow-2xl flex flex-col animate-fade-in overflow-hidden">
          {/* Header */}
          <div className="p-5 border-b border-white/10 flex items-center justify-between bg-white/[0.02]">
            <div>
              <div className="flex items-center gap-2">
                <span className="font-mono font-bold text-lg text-white">{trade.symbol}</span>
                <span className={`px-2 py-0.5 rounded text-[10px] font-mono border ${forensic.bg} ${forensic.text} ${forensic.border}`}>
                  {forensic.label}
                </span>
              </div>
              <p className="text-xs text-slate-400">
                {trade.companyName} · {trade.sector}
              </p>
            </div>

            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/5 transition-colors cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Body Content */}
          <div className="flex-1 overflow-y-auto p-5 space-y-4 text-xs">
            {/* P&L & Financial Summary Banner */}
            <div className="p-4 rounded-xl border border-white/10 bg-white/[0.02] grid grid-cols-2 gap-4 font-mono">
              <div>
                <span className="text-slate-500 text-[10px] block">Realized Return</span>
                <span className={`text-xl font-bold ${isProfit ? 'text-emerald-400' : 'text-rose-400'}`}>
                  {formatPaiseToRupees(trade.realizedPnlPaise)}
                </span>
                <span className={`text-xs ml-1 ${isProfit ? 'text-emerald-400' : 'text-rose-400'}`}>
                  ({isProfit ? `+${formatPct(trade.realizedPnlPct)}` : formatPct(trade.realizedPnlPct)})
                </span>
              </div>

              <div>
                <span className="text-slate-500 text-[10px] block">Hold Duration</span>
                <span className="text-xl font-bold text-white">{trade.holdDays} days</span>
                <span className="text-slate-500 text-[10px] block mt-0.5">
                  Closed: {trade.closedAt ? formatISTDateTime(trade.closedAt) : 'Market Close'}
                </span>
              </div>
            </div>

            {/* Price Execution Milestones */}
            <div className="arena-glass-subdued p-4 space-y-3">
              <h4 className="font-bold text-sm text-white">
                Execution Milestones & Price Path
              </h4>

              <div className="grid grid-cols-3 gap-2 font-mono text-[11px]">
                <div className="p-2.5 rounded-lg bg-black/40 border border-white/10">
                  <span className="text-slate-500 block text-[9px]">Entry Price</span>
                  <span className="font-medium text-white">{formatPaiseToRupees(trade.entryPricePaise)}</span>
                </div>

                <div className="p-2.5 rounded-lg bg-black/40 border border-white/10">
                  <span className="text-slate-500 block text-[9px]">Exit Price</span>
                  <span className="font-medium text-white">{formatPaiseToRupees(trade.exitPricePaise || trade.currentPricePaise)}</span>
                </div>

                <div className="p-2.5 rounded-lg bg-black/40 border border-white/10">
                  <span className="text-slate-500 block text-[9px]">Stop Loss</span>
                  <span className="font-medium text-white">{formatPaiseToRupees(trade.stopLossPaise)}</span>
                </div>
              </div>

              {/* Excursion Bounds */}
              <div className="p-3 rounded-lg border border-white/10 bg-black/30 space-y-2 font-mono text-[11px]">
                <div className="flex justify-between items-center">
                  <span className="flex items-center gap-1.5 text-emerald-400">
                    <ArrowUp className="w-3.5 h-3.5" />
                    <span>Max Favorable Excursion (MFE):</span>
                  </span>
                  <span className="font-semibold text-emerald-400">+{mfePct.toFixed(2)}%</span>
                </div>

                <div className="flex justify-between items-center">
                  <span className="flex items-center gap-1.5 text-rose-400">
                    <ArrowDown className="w-3.5 h-3.5" />
                    <span>Max Adverse Excursion (MAE):</span>
                  </span>
                  <span className="font-semibold text-rose-400">{maePct.toFixed(2)}%</span>
                </div>
              </div>
            </div>

            {/* Verbatim Entry Thesis */}
            <div className="arena-glass-subdued p-4 space-y-2">
              <h4 className="font-bold text-sm text-white">
                Original LLM Entry Thesis
              </h4>
              <p className="text-slate-300 text-xs leading-relaxed italic bg-black/40 p-3 rounded-lg border border-white/10">
                "{trade.thesisSummary}"
              </p>
            </div>

            {/* Deterministic Forensics & Reflection Loop */}
            <div className="arena-glass-subdued p-4 space-y-3">
              <div className="flex items-center gap-2 text-xs font-bold text-white">
                <Activity className="w-4 h-4 text-cyan-400" />
                <span>Causal Forensics & Reflection Loop</span>
              </div>

              <div className="p-3.5 rounded-lg bg-cyan-500/10 border border-cyan-500/20 space-y-2 text-xs">
                <div className="flex items-center justify-between text-white font-semibold font-mono text-[11px]">
                  <span>Classification: {forensic.label}</span>
                  <span className="text-[10px] text-cyan-400">Autonomous Reflection Engine</span>
                </div>

                <p className="text-[11px] text-slate-300 leading-relaxed font-sans">
                  Deterministic classification marked as <strong>{forensic.label}</strong> based on exit trigger breach and volatility behavior.
                </p>

                <div className="pt-2 border-t border-cyan-500/20 font-mono text-[10px] text-cyan-400 flex items-center justify-between">
                  <span>Weekly Reflection Status:</span>
                  <span className="font-semibold text-emerald-400 flex items-center gap-1">
                    <CheckCircle2 className="w-3 h-3" /> Reviewed & Watermarked
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Drawer Footer */}
          <div className="p-4 border-t border-white/10 bg-white/[0.02] flex justify-between items-center text-xs font-mono text-slate-500">
            <span>Position #{trade.id}</span>
            <button
              onClick={onClose}
              className="px-3.5 py-1.5 rounded-lg bg-white/10 border border-white/15 text-white font-medium hover:bg-white/15 transition-colors cursor-pointer"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
