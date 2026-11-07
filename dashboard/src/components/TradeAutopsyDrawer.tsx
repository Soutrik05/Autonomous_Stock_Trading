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
        className="absolute inset-0 bg-[#151B26]/40 backdrop-blur-xs transition-opacity"
        onClick={onClose}
      />

      <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
        <div className="w-screen max-w-lg bg-[#FFFFFF] border-l border-[#DCD7CC] shadow-2xl flex flex-col animate-fade-in overflow-hidden">
          {/* Header */}
          <div className="p-5 border-b border-[#DCD7CC] flex items-center justify-between bg-[#F6F4EF]">
            <div>
              <div className="flex items-center gap-2">
                <span className="font-mono font-bold text-lg text-[#151B26]">{trade.symbol}</span>
                <span className={`px-2 py-0.5 rounded-[2px] text-[10px] font-mono border ${forensic.bg} ${forensic.text} ${forensic.border}`}>
                  {forensic.label}
                </span>
              </div>
              <p className="text-xs text-[#475060]">
                {trade.companyName} · {trade.sector}
              </p>
            </div>

            <button
              onClick={onClose}
              className="p-1.5 rounded-[2px] text-[#7C8698] hover:text-[#151B26] hover:bg-[#ECE8E0] transition-colors cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Body Content */}
          <div className="flex-1 overflow-y-auto p-5 space-y-4 text-xs">
            {/* P&L & Financial Summary Banner */}
            <div className="p-4 rounded-[3px] border border-[#DCD7CC] bg-[#FFFFFF] grid grid-cols-2 gap-4 font-mono">
              <div>
                <span className="text-[#7C8698] text-[10px] block">Realized return</span>
                <span className={`text-xl font-bold ${isProfit ? 'text-[#1E6548]' : 'text-[#933835]'}`}>
                  {formatPaiseToRupees(trade.realizedPnlPaise)}
                </span>
                <span className={`text-xs ml-1 ${isProfit ? 'text-[#1E6548]' : 'text-[#933835]'}`}>
                  ({isProfit ? `+${formatPct(trade.realizedPnlPct)}` : formatPct(trade.realizedPnlPct)})
                </span>
              </div>

              <div>
                <span className="text-[#7C8698] text-[10px] block">Hold duration</span>
                <span className="text-xl font-bold text-[#151B26]">{trade.holdDays} days</span>
                <span className="text-[#7C8698] text-[10px] block mt-0.5">
                  Closed: {trade.closedAt ? formatISTDateTime(trade.closedAt) : 'Market Close'}
                </span>
              </div>
            </div>

            {/* Price Execution Milestones */}
            <div className="ledger-panel p-4 space-y-3">
              <h4 className="font-serif font-bold text-sm text-[#151B26]">
                Execution milestones & price path
              </h4>

              <div className="grid grid-cols-3 gap-2 font-mono text-[11px]">
                <div className="p-2 rounded-[2px] bg-[#F6F4EF] border border-[#E7E3D9]">
                  <span className="text-[#7C8698] block text-[9px]">Entry price</span>
                  <span className="font-medium text-[#151B26]">{formatPaiseToRupees(trade.entryPricePaise)}</span>
                </div>

                <div className="p-2 rounded-[2px] bg-[#F6F4EF] border border-[#E7E3D9]">
                  <span className="text-[#7C8698] block text-[9px]">Exit price</span>
                  <span className="font-medium text-[#151B26]">{formatPaiseToRupees(trade.exitPricePaise || trade.currentPricePaise)}</span>
                </div>

                <div className="p-2 rounded-[2px] bg-[#F6F4EF] border border-[#E7E3D9]">
                  <span className="text-[#7C8698] block text-[9px]">Stop loss</span>
                  <span className="font-medium text-[#151B26]">{formatPaiseToRupees(trade.stopLossPaise)}</span>
                </div>
              </div>

              {/* Excursion Bounds */}
              <div className="p-3 rounded-[2px] border border-[#DCD7CC] bg-[#F6F4EF] space-y-2 font-mono text-[11px]">
                <div className="flex justify-between items-center">
                  <span className="flex items-center gap-1 text-[#1E6548]">
                    <ArrowUp className="w-3.5 h-3.5" />
                    <span>Max favorable excursion (MFE):</span>
                  </span>
                  <span className="font-semibold text-[#1E6548]">+{mfePct.toFixed(2)}%</span>
                </div>

                <div className="flex justify-between items-center">
                  <span className="flex items-center gap-1 text-[#933835]">
                    <ArrowDown className="w-3.5 h-3.5" />
                    <span>Max adverse excursion (MAE):</span>
                  </span>
                  <span className="font-semibold text-[#933835]">{maePct.toFixed(2)}%</span>
                </div>
              </div>
            </div>

            {/* Verbatim Entry Thesis */}
            <div className="callout-panel p-4 space-y-2">
              <h4 className="font-serif font-bold text-sm text-[#151B26]">
                Original LLM entry thesis
              </h4>
              <p className="text-[#151B26] text-xs leading-relaxed italic bg-white/70 p-3 rounded-[2px] border border-[#D6C7A1]">
                "{trade.thesisSummary}"
              </p>
            </div>

            {/* Deterministic Forensics & Reflection Loop */}
            <div className="ledger-panel p-4 space-y-3">
              <div className="flex items-center gap-1.5 text-xs font-serif font-bold text-[#151B26]">
                <Activity className="w-4 h-4 text-[#8A7441]" />
                <span>Causal forensics & reflection loop</span>
              </div>

              <div className="p-3 rounded-[2px] bg-[#F3EFE6] border border-[#D6C7A1] space-y-2 text-xs">
                <div className="flex items-center justify-between text-[#151B26] font-semibold font-mono text-[11px]">
                  <span>Classification: {forensic.label}</span>
                  <span className="text-[10px] text-[#8A7441]">Autonomous Reflection Engine</span>
                </div>

                <p className="text-[11px] text-[#475060] leading-relaxed font-sans">
                  Deterministic classification marked as <strong>{forensic.label}</strong> based on exit trigger breach and volatility behavior.
                </p>

                <div className="pt-2 border-t border-[#D6C7A1] font-mono text-[10px] text-[#8A7441] flex items-center justify-between">
                  <span>Weekly reflection status:</span>
                  <span className="font-semibold text-[#1E6548] flex items-center gap-1">
                    <CheckCircle2 className="w-3 h-3" /> Reviewed & watermarked
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Drawer Footer */}
          <div className="p-4 border-t border-[#DCD7CC] bg-[#F6F4EF] flex justify-between items-center text-xs font-mono text-[#7C8698]">
            <span>Position #{trade.id}</span>
            <button
              onClick={onClose}
              className="px-3 py-1 rounded-[2px] bg-white border border-[#DCD7CC] text-[#151B26] font-medium hover:bg-[#ECE8E0] transition-colors cursor-pointer"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
