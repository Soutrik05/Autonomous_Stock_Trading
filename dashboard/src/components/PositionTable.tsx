import { useState } from 'react';
import type { Position } from '../types';
import { formatPaiseToRupees, formatPct, getForensicTagInfo } from '../utils/formatters';
import { ChevronDown, ChevronUp, Snowflake, Activity } from 'lucide-react';
import TradeAutopsyDrawer from './TradeAutopsyDrawer';

interface PositionTableProps {
  positions: Position[];
  title?: string;
  defaultStatus?: 'ALL' | 'OPEN' | 'CLOSED';
}

export default function PositionTable({ positions, title, defaultStatus = 'ALL' }: PositionTableProps) {
  const [filter, setFilter] = useState<'ALL' | 'OPEN' | 'CLOSED'>(defaultStatus);
  const [expandedRow, setExpandedRow] = useState<number | null>(null);
  const [autopsyTrade, setAutopsyTrade] = useState<Position | null>(null);

  const filtered = positions.filter((p) => {
    if (filter === 'ALL') return true;
    return p.status === filter;
  });

  return (
    <>
      <div className="porcelain-card overflow-hidden">
        <div className="p-4 border-b border-[#E5E2D9] flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 bg-white">
          {title && (
            <div>
              <h3 className="text-base font-serif font-bold text-[#111827]">{title}</h3>
              <p className="text-xs text-[#4B5563]">
                Click any closed trade row to inspect the full trade autopsy and excursion bounds.
              </p>
            </div>
          )}
          <div className="flex items-center gap-1.5 text-xs font-mono bg-[#F4F2EC] p-1 rounded-lg border border-[#E5E2D9]">
            {(['ALL', 'OPEN', 'CLOSED'] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setFilter(tab)}
                className={`px-3 py-1 rounded-md font-semibold transition-all cursor-pointer ${
                  filter === tab
                    ? 'bg-white text-[#111827] shadow-xs'
                    : 'text-[#4B5563] hover:text-[#111827]'
                }`}
              >
                {tab} ({tab === 'ALL' ? positions.length : positions.filter((p) => p.status === tab).length})
              </button>
            ))}
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-[#111827]">
            <thead className="bg-[#F4F2EC] uppercase font-mono font-semibold text-[11px] text-[#4B5563] tracking-wider border-b border-[#E5E2D9]">
              <tr>
                <th className="py-3 px-4">Symbol / Stock</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4 text-right">Qty</th>
                <th className="py-3 px-4 text-right">Entry (₹)</th>
                <th className="py-3 px-4 text-right">Current / Exit (₹)</th>
                <th className="py-3 px-4 text-right">Stop Loss</th>
                <th className="py-3 px-4 text-right">PnL (₹ / %)</th>
                <th className="py-3 px-4 text-center">Hold</th>
                <th className="py-3 px-4">Forensic Tag</th>
                <th className="py-3 px-2 text-center"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#EDEAE2]">
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={10} className="py-8 text-center text-[#9CA3AF] font-mono">
                    No positions match the selected filter.
                  </td>
                </tr>
              ) : (
                filtered.map((pos) => {
                  const isPositive =
                    pos.status === 'OPEN'
                      ? pos.unrealizedPnlPaise >= 0
                      : (pos.realizedPnlPaise || 0) >= 0;
                  const pnlPaise =
                    pos.status === 'OPEN' ? pos.unrealizedPnlPaise : pos.realizedPnlPaise || 0;
                  const pnlPct =
                    pos.status === 'OPEN' ? pos.unrealizedPnlPct : pos.realizedPnlPct || 0;
                  const forensic = getForensicTagInfo(pos.forensicTag);
                  const isExpanded = expandedRow === pos.id;

                  return (
                    <tr
                      key={pos.id}
                      className="hover:bg-[#F7F5EE] transition-colors cursor-pointer group"
                      onClick={() => {
                        if (pos.status === 'CLOSED') {
                          setAutopsyTrade(pos);
                        } else {
                          setExpandedRow(isExpanded ? null : pos.id);
                        }
                      }}
                    >
                      <td className="py-3.5 px-4">
                        <div className="flex items-center gap-1.5">
                          <span className="font-semibold text-[#111827] font-mono text-sm">
                            {pos.symbol}
                          </span>
                          {pos.isFrozen && (
                            <span title="Strategy frozen pending reflection review" className="text-blue-500">
                              <Snowflake className="w-3.5 h-3.5 inline animate-pulse" />
                            </span>
                          )}
                        </div>
                        <div className="text-[11px] text-[#4B5563] truncate max-w-[140px]">
                          {pos.companyName}
                        </div>
                      </td>

                      <td className="py-3.5 px-4 font-mono">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold ${
                            pos.status === 'OPEN'
                              ? 'bg-blue-50 text-blue-700 border border-blue-200'
                              : 'bg-stone-100 text-stone-700 border border-stone-200'
                          }`}
                        >
                          {pos.status}
                        </span>
                      </td>

                      <td className="py-3.5 px-4 text-right font-mono font-medium">{pos.quantity}</td>

                      <td className="py-3.5 px-4 text-right font-mono">
                        {formatPaiseToRupees(pos.entryPricePaise)}
                      </td>

                      <td className="py-3.5 px-4 text-right font-mono font-medium">
                        {formatPaiseToRupees(
                          pos.status === 'OPEN' ? pos.currentPricePaise : pos.exitPricePaise
                        )}
                      </td>

                      <td className="py-3.5 px-4 text-right font-mono text-[#4B5563]">
                        {formatPaiseToRupees(pos.stopLossPaise)}
                      </td>

                      <td className="py-3.5 px-4 text-right">
                        <div
                          className={`font-mono font-bold ${
                            isPositive ? 'text-emerald-600' : 'text-rose-600'
                          }`}
                        >
                          {formatPaiseToRupees(pnlPaise)}
                        </div>
                        <div
                          className={`text-[10px] font-mono font-semibold ${
                            isPositive ? 'text-emerald-600' : 'text-rose-600'
                          }`}
                        >
                          {formatPct(pnlPct)}
                        </div>
                      </td>

                      <td className="py-3.5 px-4 text-center font-mono text-[#4B5563]">{pos.holdDays}d</td>

                      <td className="py-3.5 px-4">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono font-semibold border ${forensic.bg} ${forensic.text} ${forensic.border}`}
                        >
                          {forensic.label}
                        </span>
                      </td>

                      <td className="py-3.5 px-2 text-center text-stone-400">
                        {pos.status === 'CLOSED' ? (
                          <span title="Open Trade Autopsy">
                            <Activity className="w-3.5 h-3.5 text-amber-600 group-hover:scale-110 transition-transform" />
                          </span>
                        ) : isExpanded ? (
                          <ChevronUp className="w-4 h-4 inline" />
                        ) : (
                          <ChevronDown className="w-4 h-4 inline" />
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Expandable Thesis Rationale Drawer for Open Positions */}
        {expandedRow !== null && (
          <div className="bg-[#F4F2EC] p-4 border-t border-[#E5E2D9] text-xs space-y-1">
            <div className="font-semibold text-[#111827] flex items-center gap-2">
              <span>Trading Thesis & Execution Rationale</span>
              <span className="font-mono text-[#9CA3AF] text-[11px]">(Position #{expandedRow})</span>
            </div>
            <p className="text-[#4B5563] leading-relaxed">
              {positions.find((p) => p.id === expandedRow)?.thesisSummary ||
                'No specific thesis recorded.'}
            </p>
          </div>
        )}
      </div>

      {/* Trade Autopsy Slide-Over Drawer */}
      <TradeAutopsyDrawer trade={autopsyTrade} onClose={() => setAutopsyTrade(null)} />
    </>
  );
}
