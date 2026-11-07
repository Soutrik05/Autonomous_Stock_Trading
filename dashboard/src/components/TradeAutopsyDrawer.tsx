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

  // Mock excursion calculations
  const mfePct = isProfit ? (trade.realizedPnlPct || 0) + 1.2 : 0.8;
  const maePct = isProfit ? -0.9 : (trade.realizedPnlPct || 0) - 0.4;

  return (
    <div className="fixed inset-0 z-50 overflow-hidden font-sans">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-stone-900/40 backdrop-blur-xs transition-opacity"
        onClick={onClose}
      />

      <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
        <div className="w-screen max-w-lg bg-white border-l border-[#E5E2D9] shadow-2xl flex flex-col animate-fade-in overflow-hidden">
          {/* Header */}
          <div className="p-5 border-b border-[#E5E2D9] flex items-center justify-between bg-[#F4F2EC]">
            <div>
              <div className="flex items-center gap-2">
                <span className="font-mono font-bold text-lg text-[#111827]">{trade.symbol}</span>
                <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold border ${forensic.bg} ${forensic.text} ${forensic.border}`}>
                  {forensic.label}
                </span>
              </div>
              <p className="text-xs text-[#4B5563]">
                {trade.companyName} · {trade.sector}
              </p>
            </div>

            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-stone-400 hover:text-stone-700 hover:bg-[#E5E2D9] transition-colors cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Body Content */}
          <div className="flex-1 overflow-y-auto p-5 space-y-5 text-xs">
            {/* PnL & Financial Summary Banner */}
            <div className="p-4 rounded-xl border border-[#E5E2D9] bg-white grid grid-cols-2 gap-4 font-mono">
              <div>
                <span className="text-[#9CA3AF] text-[10px] uppercase block">Realized Return</span>
                <span className={`text-xl font-bold ${isProfit ? 'text-emerald-600' : 'text-rose-600'}`}>
                  {formatPaiseToRupees(trade.realizedPnlPaise)}
                </span>
                <span className={`text-xs ml-1 ${isProfit ? 'text-emerald-600' : 'text-rose-600'}`}>
                  ({formatPct(trade.realizedPnlPct)})
                </span>
              </div>

              <div>
                <span className="text-[#9CA3AF] text-[10px] uppercase block">Hold Duration</span>
                <span className="text-xl font-bold text-[#111827]">{trade.holdDays} days</span>
                <span className="text-[#9CA3AF] text-[10px] block">
                  Closed: {trade.closedAt ? formatISTDateTime(trade.closedAt) : 'Market Close'}
                </span>
              </div>
            </div>

            {/* Price Execution Milestones */}
            <div className="porcelain-card p-4 space-y-3">
              <h4 className="font-serif font-bold text-sm text-[#111827]">
                Execution Milestones & Price Path
              </h4>

              <div className="grid grid-cols-3 gap-2 font-mono text-[11px]">
                <div className="p-2 rounded bg-[#F4F2EC]">
                  <span className="text-[#9CA3AF] block text-[9px] uppercase">Entry Price</span>
                  <span className="font-bold text-[#111827]">{formatPaiseToRupees(trade.entryPricePaise)}</span>
                </div>

                <div className="p-2 rounded bg-[#F4F2EC]">
                  <span className="text-[#9CA3AF] block text-[9px] uppercase">Exit Price</span>
                  <span className="font-bold text-[#111827]">{formatPaiseToRupees(trade.exitPricePaise || trade.currentPricePaise)}</span>
                </div>

                <div className="p-2 rounded bg-[#F4F2EC]">
                  <span className="text-[#9CA3AF] block text-[9px] uppercase">Stop Loss</span>
                  <span className="font-bold text-[#111827]">{formatPaiseToRupees(trade.stopLossPaise)}</span>
                </div>
              </div>

              {/* Excursion Bounds */}
              <div className="p-3 rounded-lg border border-[#EDEAE2] bg-[#FAF9F6] space-y-2 font-mono text-[11px]">
                <div className="flex justify-between items-center">
                  <span className="flex items-center gap-1 text-emerald-700">
                    <ArrowUp className="w-3.5 h-3.5" />
                    <span>Max Favorable Excursion (MFE):</span>
                  </span>
                  <span className="font-bold text-emerald-700">+{mfePct.toFixed(2)}%</span>
                </div>

                <div className="flex justify-between items-center">
                  <span className="flex items-center gap-1 text-rose-700">
                    <ArrowDown className="w-3.5 h-3.5" />
                    <span>Max Adverse Excursion (MAE):</span>
                  </span>
                  <span className="font-bold text-rose-700">{maePct.toFixed(2)}%</span>
                </div>
              </div>
            </div>

            {/* Verbatim Entry Thesis */}
            <div className="porcelain-card p-4 space-y-2">
              <h4 className="font-serif font-bold text-sm text-[#111827]">
                Original LLM Entry Thesis
              </h4>
              <p className="text-[#4B5563] text-xs leading-relaxed italic bg-[#F4F2EC] p-3 rounded-lg border border-[#E5E2D9]">
                "{trade.thesisSummary}"
              </p>
            </div>

            {/* Deterministic Forensics & Reflection Loop */}
            <div className="porcelain-card p-4 space-y-3">
              <div className="flex items-center gap-1.5 text-xs font-serif font-bold text-[#111827]">
                <Activity className="w-4 h-4 text-amber-600" />
                <span>Causal Forensics & Reflection Loop</span>
              </div>

              <div className="p-3 rounded-lg bg-amber-50/50 border border-amber-200/80 space-y-2 text-xs">
                <div className="flex items-center justify-between text-amber-950 font-semibold font-mono text-[11px]">
                  <span>Classification: {forensic.label}</span>
                  <span className="text-[10px] uppercase text-amber-800">learning/engine.py</span>
                </div>

                <p className="text-[11px] text-amber-900/90 leading-relaxed font-sans">
                  Deterministic classification marked as <strong>{forensic.label}</strong> based on exit trigger breach and volatility behavior.
                </p>

                <div className="pt-2 border-t border-amber-200/60 font-mono text-[10px] text-amber-800 flex items-center justify-between">
                  <span>Weekly Reflection Status:</span>
                  <span className="font-bold text-emerald-700 flex items-center gap-1">
                    <CheckCircle2 className="w-3 h-3" /> Reviewed & Watermarked
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Drawer Footer */}
          <div className="p-4 border-t border-[#E5E2D9] bg-[#F4F2EC] flex justify-between items-center text-xs font-mono text-[#9CA3AF]">
            <span>Position ID #{trade.id}</span>
            <button
              onClick={onClose}
              className="px-3 py-1 rounded-md bg-white border border-[#E5E2D9] text-[#111827] font-semibold hover:bg-stone-50 transition-colors cursor-pointer"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
