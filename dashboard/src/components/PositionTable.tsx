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
      <div className="arena-glass overflow-hidden shadow-2xl">
        <div className="p-5 border-b border-white/10 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 bg-white/[0.02]">
          {title && (
            <div>
              <h3 className="text-base font-bold text-white">{title}</h3>
              <p className="text-xs text-slate-400">
                Click any closed trade row to inspect the full trade autopsy and excursion bounds.
              </p>
            </div>
          )}
          <div className="flex items-center gap-1 text-xs font-mono bg-white/[0.04] p-1 rounded border border-white/10">
            {(['ALL', 'OPEN', 'CLOSED'] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setFilter(tab)}
                className={`px-3 py-1.5 rounded transition-all cursor-pointer ${
                  filter === tab
                    ? 'bg-blue-600 text-white font-semibold'
                    : 'text-slate-400 hover:text-white hover:bg-white/[0.04]'
                }`}
              >
                {tab === 'ALL' ? 'All' : tab === 'OPEN' ? 'Open' : 'Closed'} (
                {tab === 'ALL' ? positions.length : positions.filter((p) => p.status === tab).length})
              </button>
            ))}
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono text-slate-200">
            <thead className="bg-white/[0.02] text-[11px] text-slate-400 border-b border-white/10">
              <tr>
                <th className="py-3 px-4 font-semibold">Symbol / Company</th>
                <th className="py-3 px-4 font-semibold">Status</th>
                <th className="py-3 px-4 text-right font-semibold">Qty</th>
                <th className="py-3 px-4 text-right font-semibold">Entry (₹)</th>
                <th className="py-3 px-4 text-right font-semibold">Current / Exit (₹)</th>
                <th className="py-3 px-4 text-right font-semibold">Stop Loss</th>
                <th className="py-3 px-4 text-right font-semibold">P&L (₹ / %)</th>
                <th className="py-3 px-4 text-center font-semibold">Hold</th>
                <th className="py-3 px-4 font-semibold">Forensic Tag</th>
                <th className="py-3 px-2 text-center font-semibold"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={10} className="py-8 text-center text-slate-500 font-mono">
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
                      className="hover:bg-white/[0.04] transition-colors cursor-pointer group"
                      onClick={() => {
                        if (pos.status === 'CLOSED') {
                          setAutopsyTrade(pos);
                        } else {
                          setExpandedRow(isExpanded ? null : pos.id);
                        }
                      }}
                    >
                      <td className="py-3.5 px-4">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-white text-xs">
                            {pos.symbol}
                          </span>
                          {pos.isFrozen && (
                            <span title="Strategy frozen pending reflection review" className="text-blue-400">
                              <Snowflake className="w-3.5 h-3.5 inline animate-pulse" />
                            </span>
                          )}
                        </div>
                        <div className="text-[11px] text-slate-400 truncate max-w-[150px]">
                          {pos.companyName}
                        </div>
                      </td>

                      <td className="py-3.5 px-4">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium border ${
                            pos.status === 'OPEN'
                              ? 'bg-blue-500/15 text-blue-300 border-blue-500/30'
                              : 'bg-white/5 text-slate-400 border-white/10'
                          }`}
                        >
                          {pos.status === 'OPEN' ? 'Open' : 'Closed'}
                        </span>
                      </td>

                      <td className="py-3.5 px-4 text-right text-white font-medium">{pos.quantity}</td>

                      <td className="py-3.5 px-4 text-right text-slate-400">
                        {formatPaiseToRupees(pos.entryPricePaise)}
                      </td>

                      <td className="py-3.5 px-4 text-right text-white font-semibold">
                        {formatPaiseToRupees(
                          pos.status === 'OPEN' ? pos.currentPricePaise : pos.exitPricePaise
                        )}
                      </td>

                      <td className="py-3.5 px-4 text-right text-slate-500">
                        {formatPaiseToRupees(pos.stopLossPaise)}
                      </td>

                      <td className="py-3.5 px-4 text-right">
                        <div
                          className={`font-semibold ${
                            isPositive ? 'text-emerald-400' : 'text-rose-400'
                          }`}
                        >
                          {formatPaiseToRupees(pnlPaise)}
                        </div>
                        <div
                          className={`text-[10px] font-medium ${
                            isPositive ? 'text-emerald-400' : 'text-rose-400'
                          }`}
                        >
                          {formatPct(pnlPct)}
                        </div>
                      </td>

                      <td className="py-3.5 px-4 text-center text-slate-400">{pos.holdDays}d</td>

                      <td className="py-3.5 px-4">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] border ${forensic.bg} ${forensic.text} ${forensic.border}`}
                        >
                          {forensic.label}
                        </span>
                      </td>

                      <td className="py-3.5 px-2 text-center text-slate-500">
                        {pos.status === 'CLOSED' ? (
                          <span title="Open Trade Autopsy">
                            <Activity className="w-3.5 h-3.5 text-blue-400 group-hover:scale-110 transition-transform" />
                          </span>
                        ) : isExpanded ? (
                          <ChevronUp className="w-3.5 h-3.5 inline" />
                        ) : (
                          <ChevronDown className="w-3.5 h-3.5 inline" />
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
          <div className="arena-glass-subdued p-5 border-t border-white/10 text-xs space-y-2 m-4 rounded">
            <div className="font-semibold text-white flex items-center gap-2">
              <span>Trading Thesis & Execution Rationale</span>
              <span className="font-mono text-blue-400 text-[11px]">(Position #{expandedRow})</span>
            </div>
            <p className="text-slate-300 leading-relaxed font-sans">
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
