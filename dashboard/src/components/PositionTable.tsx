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
      <div className="ledger-panel overflow-hidden">
        <div className="p-4 border-b border-[#E7E3D9] flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 bg-white">
          {title && (
            <div>
              <h3 className="text-base font-serif font-bold text-[#151B26]">{title}</h3>
              <p className="text-xs text-[#7C8698]">
                Click any closed trade row to inspect the full trade autopsy and excursion bounds.
              </p>
            </div>
          )}
          <div className="flex items-center gap-1 text-xs font-mono bg-[#F6F4EF] p-1 rounded-[3px] border border-[#DCD7CC]">
            {(['ALL', 'OPEN', 'CLOSED'] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setFilter(tab)}
                className={`px-3 py-1 rounded-[2px] transition-colors cursor-pointer ${
                  filter === tab
                    ? 'bg-white font-medium text-[#151B26] shadow-xs border border-[#DCD7CC]'
                    : 'text-[#475060] hover:text-[#151B26]'
                }`}
              >
                {tab === 'ALL' ? 'All' : tab === 'OPEN' ? 'Open' : 'Closed'} (
                {tab === 'ALL' ? positions.length : positions.filter((p) => p.status === tab).length})
              </button>
            ))}
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-[#151B26]">
            <thead className="bg-[#F6F4EF] font-mono text-[11px] text-[#475060] border-b border-[#DCD7CC]">
              <tr>
                <th className="py-2.5 px-4 font-medium">Symbol / Company</th>
                <th className="py-2.5 px-4 font-medium">Status</th>
                <th className="py-2.5 px-4 text-right font-medium">Qty</th>
                <th className="py-2.5 px-4 text-right font-medium">Entry (₹)</th>
                <th className="py-2.5 px-4 text-right font-medium">Current / Exit (₹)</th>
                <th className="py-2.5 px-4 text-right font-medium">Stop loss</th>
                <th className="py-2.5 px-4 text-right font-medium">P&L (₹ / %)</th>
                <th className="py-2.5 px-4 text-center font-medium">Hold</th>
                <th className="py-2.5 px-4 font-medium">Forensic tag</th>
                <th className="py-2.5 px-2 text-center font-medium"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E7E3D9]">
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={10} className="py-8 text-center text-[#7C8698] font-mono">
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
                      className="hover:bg-[#F6F4EF] transition-colors cursor-pointer group"
                      onClick={() => {
                        if (pos.status === 'CLOSED') {
                          setAutopsyTrade(pos);
                        } else {
                          setExpandedRow(isExpanded ? null : pos.id);
                        }
                      }}
                    >
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-1.5">
                          <span className="font-semibold text-[#151B26] font-mono text-xs">
                            {pos.symbol}
                          </span>
                          {pos.isFrozen && (
                            <span title="Strategy frozen pending reflection review" className="text-[#2A4B7C]">
                              <Snowflake className="w-3.5 h-3.5 inline animate-pulse" />
                            </span>
                          )}
                        </div>
                        <div className="text-[11px] text-[#7C8698] truncate max-w-[150px]">
                          {pos.companyName}
                        </div>
                      </td>

                      <td className="py-3 px-4 font-mono">
                        <span
                          className={`inline-flex items-center px-1.5 py-0.5 rounded-[2px] text-[10px] font-medium border ${
                            pos.status === 'OPEN'
                              ? 'bg-[#EDF2F9] text-[#2A4B7C] border-[#B9C9E1]'
                              : 'bg-[#F6F4EF] text-[#475060] border-[#DCD7CC]'
                          }`}
                        >
                          {pos.status === 'OPEN' ? 'Open' : 'Closed'}
                        </span>
                      </td>

                      <td className="py-3 px-4 text-right font-mono text-[#151B26]">{pos.quantity}</td>

                      <td className="py-3 px-4 text-right font-mono text-[#475060]">
                        {formatPaiseToRupees(pos.entryPricePaise)}
                      </td>

                      <td className="py-3 px-4 text-right font-mono text-[#151B26]">
                        {formatPaiseToRupees(
                          pos.status === 'OPEN' ? pos.currentPricePaise : pos.exitPricePaise
                        )}
                      </td>

                      <td className="py-3 px-4 text-right font-mono text-[#7C8698]">
                        {formatPaiseToRupees(pos.stopLossPaise)}
                      </td>

                      <td className="py-3 px-4 text-right font-mono">
                        <div
                          className={`font-semibold ${
                            isPositive ? 'text-[#1E6548]' : 'text-[#933835]'
                          }`}
                        >
                          {formatPaiseToRupees(pnlPaise)}
                        </div>
                        <div
                          className={`text-[10px] font-medium ${
                            isPositive ? 'text-[#1E6548]' : 'text-[#933835]'
                          }`}
                        >
                          {isPositive ? `+${formatPct(pnlPct)}` : formatPct(pnlPct)}
                        </div>
                      </td>

                      <td className="py-3 px-4 text-center font-mono text-[#475060]">{pos.holdDays}d</td>

                      <td className="py-3 px-4">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded-[2px] text-[10px] font-mono border ${forensic.bg} ${forensic.text} ${forensic.border}`}
                        >
                          {forensic.label}
                        </span>
                      </td>

                      <td className="py-3 px-2 text-center text-[#7C8698]">
                        {pos.status === 'CLOSED' ? (
                          <span title="Open Trade Autopsy">
                            <Activity className="w-3.5 h-3.5 text-[#8A7441] group-hover:scale-110 transition-transform" />
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
          <div className="callout-panel p-4 text-xs space-y-1.5 m-3">
            <div className="font-semibold text-[#151B26] flex items-center gap-2">
              <span>Trading thesis & execution rationale</span>
              <span className="font-mono text-[#7C8698] text-[11px]">(Position #{expandedRow})</span>
            </div>
            <p className="text-[#475060] leading-relaxed">
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
