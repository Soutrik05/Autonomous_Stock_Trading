import { useState } from 'react';
import type { Position } from '../types';
import { formatPaiseToRupees, formatPct, getForensicTagInfo } from '../utils/formatters';
import { Snowflake, ChevronDown, ChevronUp } from 'lucide-react';

interface PositionTableProps {
  positions: Position[];
  title?: string;
}

export default function PositionTable({ positions, title }: PositionTableProps) {
  const [filter, setFilter] = useState<'ALL' | 'OPEN' | 'CLOSED'>('ALL');
  const [expandedRow, setExpandedRow] = useState<number | null>(null);

  const filtered = positions.filter((p) => {
    if (filter === 'ALL') return true;
    return p.status === filter;
  });

  return (
    <div className="bg-white dark:bg-stone-900 rounded-xl border border-stone-200 dark:border-stone-800 shadow-sm overflow-hidden">
      <div className="p-4 border-b border-stone-200 dark:border-stone-800 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
        {title && <h3 className="text-base font-semibold text-stone-900 dark:text-stone-100">{title}</h3>}
        <div className="flex items-center gap-1.5 text-xs bg-stone-100 dark:bg-stone-800 p-1 rounded-lg">
          {(['ALL', 'OPEN', 'CLOSED'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setFilter(tab)}
              className={`px-3 py-1 rounded-md font-medium transition-all ${
                filter === tab
                  ? 'bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 shadow-xs'
                  : 'text-stone-500 dark:text-stone-400 hover:text-stone-800 dark:hover:text-stone-200'
              }`}
            >
              {tab} ({tab === 'ALL' ? positions.length : positions.filter((p) => p.status === tab).length})
            </button>
          ))}
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs text-stone-700 dark:text-stone-300">
          <thead className="bg-stone-50 dark:bg-stone-800/60 uppercase font-semibold text-[11px] text-stone-500 dark:text-stone-400 tracking-wider">
            <tr>
              <th className="py-3 px-4">Symbol / Stock</th>
              <th className="py-3 px-4">Status</th>
              <th className="py-3 px-4 text-right">Qty</th>
              <th className="py-3 px-4 text-right">Entry (₹)</th>
              <th className="py-3 px-4 text-right">Current / Exit (₹)</th>
              <th className="py-3 px-4 text-right">Stop Loss</th>
              <th className="py-3 px-4 text-right">PnL (₹ / %)</th>
              <th className="py-3 px-4">Hold Days</th>
              <th className="py-3 px-4">Forensic Category</th>
              <th className="py-3 px-2 text-center"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-stone-100 dark:divide-stone-800/80">
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={10} className="py-8 text-center text-stone-400 dark:text-stone-500">
                  No positions match the selected filter.
                </td>
              </tr>
            ) : (
              filtered.map((pos) => {
                const isPositive = pos.status === 'OPEN' ? pos.unrealizedPnlPaise >= 0 : (pos.realizedPnlPaise || 0) >= 0;
                const pnlPaise = pos.status === 'OPEN' ? pos.unrealizedPnlPaise : (pos.realizedPnlPaise || 0);
                const pnlPct = pos.status === 'OPEN' ? pos.unrealizedPnlPct : (pos.realizedPnlPct || 0);
                const forensic = getForensicTagInfo(pos.forensicTag);
                const isExpanded = expandedRow === pos.id;

                return (
                  <tr
                    key={pos.id}
                    className="hover:bg-stone-50/70 dark:hover:bg-stone-800/40 transition-colors cursor-pointer group"
                    onClick={() => setExpandedRow(isExpanded ? null : pos.id)}
                  >
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-1.5">
                        <span className="font-semibold text-stone-900 dark:text-stone-100 font-mono text-sm">
                          {pos.symbol}
                        </span>
                        {pos.isFrozen && (
                          <span title="Frozen: Strategy frozen pending reflection review" className="text-blue-500">
                            <Snowflake className="w-3.5 h-3.5 inline animate-pulse" />
                          </span>
                        )}
                      </div>
                      <div className="text-[11px] text-stone-400 dark:text-stone-500 truncate max-w-[140px]">
                        {pos.companyName} · {pos.sector}
                      </div>
                    </td>

                    <td className="py-3 px-4">
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold ${
                          pos.status === 'OPEN'
                            ? 'bg-blue-50 text-blue-700 dark:bg-blue-950/50 dark:text-blue-300 border border-blue-200 dark:border-blue-800'
                            : 'bg-stone-100 text-stone-600 dark:bg-stone-800 dark:text-stone-400 border border-stone-200 dark:border-stone-700'
                        }`}
                      >
                        {pos.status}
                      </span>
                    </td>

                    <td className="py-3 px-4 text-right font-mono font-medium">{pos.quantity}</td>

                    <td className="py-3 px-4 text-right font-mono">
                      {formatPaiseToRupees(pos.entryPricePaise)}
                    </td>

                    <td className="py-3 px-4 text-right font-mono">
                      {formatPaiseToRupees(pos.status === 'OPEN' ? pos.currentPricePaise : pos.exitPricePaise)}
                    </td>

                    <td className="py-3 px-4 text-right font-mono text-stone-500 dark:text-stone-400">
                      {formatPaiseToRupees(pos.stopLossPaise)}
                    </td>

                    <td className="py-3 px-4 text-right">
                      <div className={`font-mono font-semibold ${isPositive ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>
                        {formatPaiseToRupees(pnlPaise)}
                      </div>
                      <div className={`text-[10px] font-mono ${isPositive ? 'text-emerald-600/80 dark:text-emerald-400/80' : 'text-rose-600/80 dark:text-rose-400/80'}`}>
                        {formatPct(pnlPct)}
                      </div>
                    </td>

                    <td className="py-3 px-4 font-mono">{pos.holdDays}d</td>

                    <td className="py-3 px-4">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium ${forensic.bg} ${forensic.text}`}>
                        {forensic.label}
                      </span>
                    </td>

                    <td className="py-3 px-2 text-center text-stone-400">
                      {isExpanded ? <ChevronUp className="w-4 h-4 inline" /> : <ChevronDown className="w-4 h-4 inline" />}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Expanded Row Drawer / Thesis Inspection */}
      {expandedRow !== null && (
        <div className="bg-stone-50 dark:bg-stone-800/80 p-4 border-t border-stone-200 dark:border-stone-700 text-xs text-stone-700 dark:text-stone-300">
          <div className="font-semibold text-stone-900 dark:text-stone-100 mb-1 flex items-center gap-2">
            <span>Trading Thesis & Execution Rationale</span>
            <span className="font-mono text-stone-400 text-[11px]">(Position #{expandedRow})</span>
          </div>
          <p className="leading-relaxed">
            {positions.find((p) => p.id === expandedRow)?.thesisSummary || 'No specific thesis recorded.'}
          </p>
        </div>
      )}
    </div>
  );
}
