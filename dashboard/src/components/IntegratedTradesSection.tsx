import React, { useState } from 'react';
import type { Position, Decision, Order } from '../types';
import { formatPaiseToRupees, formatPct, formatISTDateTime } from '../utils/formatters';
import { ChevronDown, ChevronUp, Brain, Activity } from 'lucide-react';
import { SectionHeader } from './ui/SectionHeader';
import TradeAutopsyDrawer from './TradeAutopsyDrawer';
import { cn } from '../utils/cn';

interface IntegratedTradesSectionProps {
  positions: Position[];
  decisions: Decision[];
  orders: Order[];
}

export default function IntegratedTradesSection({
  positions,
  decisions,
  orders,
}: IntegratedTradesSectionProps) {
  const [viewTab, setViewTab] = useState<'TRADES' | 'DECISIONS'>(() => {
    return positions.length === 0 && decisions.length > 0 ? 'DECISIONS' : 'TRADES';
  });
  const [filterMode, setFilterMode] = useState<'ALL' | 'OPEN' | 'CLOSED'>('ALL');
  const [expandedTradeId, setExpandedTradeId] = useState<number | null>(null);
  const [expandedDecisionId, setExpandedDecisionId] = useState<number | null>(null);
  const [autopsyPosition, setAutopsyPosition] = useState<Position | null>(null);

  // Map decisions and orders by symbol for instant lookup
  const decisionMap = new Map<string, Decision>();
  decisions.forEach((d) => {
    if (!decisionMap.has(d.symbol)) {
      decisionMap.set(d.symbol, d);
    }
  });

  const orderMap = new Map<string, Order[]>();
  orders.forEach((o) => {
    const list = orderMap.get(o.symbol) || [];
    list.push(o);
    orderMap.set(o.symbol, list);
  });

  const filteredPositions = positions.filter((p) => {
    if (filterMode === 'OPEN') return p.status === 'OPEN';
    if (filterMode === 'CLOSED') return p.status === 'CLOSED';
    return true;
  });

  const openCount = positions.filter((p) => p.status === 'OPEN').length;
  const closedCount = positions.filter((p) => p.status === 'CLOSED').length;

  return (
    <section className="space-y-4 font-sans">
      {/* Section Header (Clean, minimal, no subtitles above) */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 border-b border-border-hairline pb-3">
        <SectionHeader
          title="Trade Execution & Decision Ledger"
          tag="AUDITED TELEMETRY"
        />

        {/* Tab & Filter Controls */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Main View Mode Selector */}
          <div className="flex items-center p-0.5 rounded bg-[#121212] border border-border-hairline text-xs font-mono">
            <button
              onClick={() => setViewTab('TRADES')}
              className={cn(
                "px-3 py-1 rounded transition-colors cursor-pointer",
                viewTab === 'TRADES'
                  ? "bg-white/15 text-white font-medium"
                  : "text-zinc-400 hover:text-white"
              )}
            >
              Active Trades ({positions.length})
            </button>
            <button
              onClick={() => setViewTab('DECISIONS')}
              className={cn(
                "px-3 py-1 rounded transition-colors cursor-pointer flex items-center gap-1.5",
                viewTab === 'DECISIONS'
                  ? "bg-accent/15 text-accent font-semibold border border-accent/30"
                  : "text-zinc-400 hover:text-white"
              )}
            >
              <Brain className="w-3.5 h-3.5 text-accent" />
              <span>Decisions ({decisions.length})</span>
            </button>
          </div>

          {/* Sub-Filter for Trades */}
          {viewTab === 'TRADES' && positions.length > 0 && (
            <div className="flex items-center gap-1 p-0.5 rounded bg-[#121212] border border-border-hairline text-xs font-mono">
              <button
                onClick={() => setFilterMode('ALL')}
                className={cn(
                  "px-2 py-0.5 rounded transition-colors cursor-pointer",
                  filterMode === 'ALL'
                    ? "bg-white/15 text-white font-medium"
                    : "text-zinc-400 hover:text-white"
                )}
              >
                All
              </button>
              <button
                onClick={() => setFilterMode('OPEN')}
                className={cn(
                  "px-2 py-0.5 rounded transition-colors cursor-pointer",
                  filterMode === 'OPEN'
                    ? "bg-white/15 text-white font-medium"
                    : "text-zinc-400 hover:text-white"
                )}
              >
                Open ({openCount})
              </button>
              <button
                onClick={() => setFilterMode('CLOSED')}
                className={cn(
                  "px-2 py-0.5 rounded transition-colors cursor-pointer",
                  filterMode === 'CLOSED'
                    ? "bg-white/15 text-white font-medium"
                    : "text-zinc-400 hover:text-white"
                )}
              >
                Settled ({closedCount})
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Main Content Area: Institutional Minimalist Tables */}
      {viewTab === 'TRADES' ? (
        filteredPositions.length === 0 ? (
          <div className="p-8 text-center bg-[#161616] border border-border-hairline rounded-lg text-zinc-500 font-mono text-xs">
            No trade execution records found matching the active filter.
          </div>
        ) : (
          <div className="border border-border-hairline bg-[#161616] rounded-lg overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left font-mono text-xs">
                <thead>
                  <tr className="bg-[#121212] border-b border-border-hairline text-[10px] text-zinc-500 uppercase tracking-wider">
                    <th className="py-2.5 px-4 font-normal">Status</th>
                    <th className="py-2.5 px-4 font-normal">Symbol</th>
                    <th className="py-2.5 px-4 font-normal text-right">Shares</th>
                    <th className="py-2.5 px-4 font-normal text-right">Entry Basis</th>
                    <th className="py-2.5 px-4 font-normal text-right">LTP / Exit</th>
                    <th className="py-2.5 px-4 font-normal text-right">P&L (INR)</th>
                    <th className="py-2.5 px-4 font-normal text-right">P&L (%)</th>
                    <th className="py-2.5 px-4 font-normal text-right">Stop Loss</th>
                    <th className="py-2.5 px-4 font-normal text-center">Audit</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border-hairline text-zinc-300">
                  {filteredPositions.map((pos) => {
                    const isClosed = pos.status === 'CLOSED';
                    const decision = decisionMap.get(pos.symbol);
                    const relatedOrders = orderMap.get(pos.symbol) || [];

                    const pnlPaise = isClosed
                      ? pos.realizedPnlPaise ?? 0
                      : pos.unrealizedPnlPaise;
                    const pnlPct = isClosed
                      ? pos.realizedPnlPct ?? 0
                      : pos.unrealizedPnlPct;
                    const isProfit = pnlPaise >= 0;
                    const isExpanded = expandedTradeId === pos.id;

                    const rationaleText =
                      pos.thesisSummary ||
                      decision?.rationale ||
                      'Strategy entry conditions fulfilled according to quantitative investment tenets.';

                    return (
                      <React.Fragment key={pos.id}>
                        <tr
                          onClick={() => setExpandedTradeId(isExpanded ? null : pos.id)}
                          className="hover:bg-white/[0.02] transition-colors cursor-pointer"
                        >
                          {/* Status */}
                          <td className="py-3 px-4">
                            <span
                              className={cn(
                                "inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-mono tracking-wider font-medium border",
                                isClosed
                                  ? "border-border-hairline text-zinc-400 bg-transparent"
                                  : "border-white/20 text-zinc-200 bg-white/[0.04]"
                              )}
                            >
                              {!isClosed && <span className="w-1.5 h-1.5 rounded-full bg-positive" />}
                              {isClosed ? 'SETTLED' : 'OPEN'}
                            </span>
                          </td>

                          {/* Symbol & Company */}
                          <td className="py-3 px-4 font-sans">
                            <div className="flex items-center gap-2">
                              <span className="font-mono font-semibold text-white text-xs">
                                {pos.symbol}
                              </span>
                              <span className="text-zinc-400 text-xs truncate max-w-[140px] sm:max-w-[200px]">
                                {pos.companyName || pos.sector}
                              </span>
                            </div>
                          </td>

                          {/* Shares */}
                          <td className="py-3 px-4 text-right tabular-nums text-zinc-200">
                            {pos.quantity}
                          </td>

                          {/* Entry Basis */}
                          <td className="py-3 px-4 text-right tabular-nums text-zinc-300">
                            {formatPaiseToRupees(pos.entryPricePaise)}
                          </td>

                          {/* LTP / Exit */}
                          <td className="py-3 px-4 text-right tabular-nums font-medium text-white">
                            {formatPaiseToRupees(
                              isClosed && pos.exitPricePaise ? pos.exitPricePaise : pos.currentPricePaise
                            )}
                          </td>

                          {/* P&L INR */}
                          <td
                            className={cn(
                              "py-3 px-4 text-right tabular-nums font-semibold",
                              isProfit ? "text-positive" : "text-negative"
                            )}
                          >
                            {isProfit ? '+' : ''}{formatPaiseToRupees(pnlPaise)}
                          </td>

                          {/* P&L % */}
                          <td
                            className={cn(
                              "py-3 px-4 text-right tabular-nums font-semibold",
                              isProfit ? "text-positive" : "text-negative"
                            )}
                          >
                            {formatPct(pnlPct)}
                          </td>

                          {/* Stop Loss */}
                          <td className="py-3 px-4 text-right tabular-nums text-zinc-400 text-[11px]">
                            {pos.stopLossPaise > 0 ? formatPaiseToRupees(pos.stopLossPaise) : '—'}
                          </td>

                          {/* Expand Caret */}
                          <td className="py-3 px-4 text-center text-zinc-500">
                            {isExpanded ? (
                              <ChevronUp className="w-3.5 h-3.5 inline-block text-white" />
                            ) : (
                              <ChevronDown className="w-3.5 h-3.5 inline-block" />
                            )}
                          </td>
                        </tr>

                        {/* Expanded Drawer: Clean Monospace Thesis & Orders */}
                        {isExpanded && (
                          <tr className="bg-[#121212]/80">
                            <td colSpan={9} className="p-4 border-b border-border-hairline space-y-3">
                              {/* Rationale Prose */}
                              <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2 border-l-2 border-accent pl-3 py-1">
                                <p className="text-xs text-zinc-200 italic leading-relaxed font-sans">
                                  "{rationaleText}"
                                </p>
                                {isClosed && (
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      setAutopsyPosition(pos);
                                    }}
                                    className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#161616] border border-border-hairline hover:border-accent/40 text-accent font-mono text-[11px] transition-colors cursor-pointer flex-shrink-0"
                                  >
                                    <Activity className="w-3.5 h-3.5" />
                                    <span>Forensic Autopsy</span>
                                  </button>
                                )}
                              </div>

                              {/* Limit Orders Trail */}
                              {relatedOrders.length > 0 && (
                                <div className="pt-2 border-t border-border-hairline overflow-x-auto">
                                  <table className="w-full text-left font-mono text-[11px] text-zinc-400">
                                    <thead>
                                      <tr className="text-zinc-500 border-b border-border-hairline text-[10px] uppercase">
                                        <th className="py-1 px-2">Order</th>
                                        <th className="py-1 px-2">Side</th>
                                        <th className="py-1 px-2 text-right">Shares</th>
                                        <th className="py-1 px-2 text-right">Limit Price</th>
                                        <th className="py-1 px-2 text-right">Filled Price</th>
                                        <th className="py-1 px-2">Status</th>
                                        <th className="py-1 px-2 text-right">Timestamp</th>
                                      </tr>
                                    </thead>
                                    <tbody className="divide-y divide-border-hairline">
                                      {relatedOrders.map((ord) => (
                                        <tr key={ord.id}>
                                          <td className="py-1 px-2 text-zinc-400">#{ord.id}</td>
                                          <td className="py-1 px-2">
                                            <span
                                              className={cn(
                                                "px-1.5 py-0.2 rounded text-[9px] font-semibold",
                                                ord.side === 'BUY' ? "text-positive" : "text-negative"
                                              )}
                                            >
                                              {ord.side}
                                            </span>
                                          </td>
                                          <td className="py-1 px-2 text-right tabular-nums">{ord.quantity}</td>
                                          <td className="py-1 px-2 text-right tabular-nums">{formatPaiseToRupees(ord.limitPricePaise)}</td>
                                          <td className="py-1 px-2 text-right tabular-nums text-white">
                                            {ord.filledPricePaise ? formatPaiseToRupees(ord.filledPricePaise) : '—'}
                                          </td>
                                          <td className="py-1 px-2 text-zinc-300">{ord.status}</td>
                                          <td className="py-1 px-2 text-right text-zinc-500">
                                            {formatISTDateTime(ord.submittedAt)}
                                          </td>
                                        </tr>
                                      ))}
                                    </tbody>
                                  </table>
                                </div>
                              )}
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )
      ) : (
        /* Decisions Tab */
        decisions.length === 0 ? (
          <div className="p-8 text-center bg-[#161616] border border-border-hairline rounded-lg text-zinc-500 font-mono text-xs">
            No candidate decisions recorded yet for this strategy.
          </div>
        ) : (
          <div className="border border-border-hairline bg-[#161616] rounded-lg overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left font-mono text-xs">
                <thead>
                  <tr className="bg-[#121212] border-b border-border-hairline text-[10px] text-zinc-500 uppercase tracking-wider">
                    <th className="py-2.5 px-4 font-normal">Action</th>
                    <th className="py-2.5 px-4 font-normal">Symbol</th>
                    <th className="py-2.5 px-4 font-normal">Date</th>
                    <th className="py-2.5 px-4 font-normal text-right">Faithfulness</th>
                    <th className="py-2.5 px-4 font-normal text-right">Fidelity</th>
                    <th className="py-2.5 px-4 font-normal">Thesis Rationale</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border-hairline text-zinc-300">
                  {decisions.map((dec) => {
                    const isBuy = dec.action === 'BUY';
                    const isHold = dec.action === 'HOLD';
                    const isExpanded = expandedDecisionId === dec.id;

                    return (
                      <React.Fragment key={dec.id}>
                        <tr
                          onClick={() => setExpandedDecisionId(isExpanded ? null : dec.id)}
                          className="hover:bg-white/[0.02] transition-colors cursor-pointer"
                        >
                          {/* Action */}
                          <td className="py-3 px-4">
                            <span
                              className={cn(
                                "px-2 py-0.5 rounded text-[10px] font-semibold tracking-wider border",
                                isBuy
                                  ? "border-emerald-500/30 text-positive bg-emerald-500/10"
                                  : isHold
                                  ? "border-amber-500/30 text-amber-300 bg-amber-500/10"
                                  : "border-rose-500/30 text-negative bg-rose-500/10"
                              )}
                            >
                              {dec.action}
                            </span>
                          </td>

                          {/* Symbol */}
                          <td className="py-3 px-4 font-semibold text-white font-mono">
                            {dec.symbol}
                          </td>

                          {/* Date */}
                          <td className="py-3 px-4 text-zinc-400 text-[11px]">
                            {dec.decisionDate}
                          </td>

                          {/* Faithfulness */}
                          <td className="py-3 px-4 text-right tabular-nums text-purple-400 font-semibold">
                            {(dec.faithfulnessScore * 100).toFixed(0)}%
                          </td>

                          {/* Sizing Fidelity */}
                          <td className="py-3 px-4 text-right tabular-nums text-accent font-semibold">
                            {dec.sizingFidelityScore !== undefined && dec.sizingFidelityScore !== null
                              ? `${(dec.sizingFidelityScore * 100).toFixed(0)}%`
                              : '—'}
                          </td>

                          {/* Thesis Preview */}
                          <td className="py-3 px-4 font-sans text-xs text-zinc-300 truncate max-w-[280px] sm:max-w-[420px]">
                            {dec.rationale}
                          </td>
                        </tr>

                        {/* Expanded Full Decision Details */}
                        {isExpanded && (
                          <tr className="bg-[#121212]/80">
                            <td colSpan={6} className="p-4 border-b border-border-hairline space-y-2.5">
                              <div className="border-l-2 border-accent pl-3 py-1">
                                <p className="text-xs text-zinc-200 italic leading-relaxed font-sans">
                                  "{dec.rationale}"
                                </p>
                              </div>

                              {dec.preMortemRisk && (
                                <div className="text-xs text-zinc-400 font-sans pt-1">
                                  <span className="text-negative font-mono font-medium mr-1.5 uppercase text-[10px]">
                                    Risk Hurdle:
                                  </span>
                                  {dec.preMortemRisk}
                                </div>
                              )}

                              {dec.citedMetrics && dec.citedMetrics.length > 0 && (
                                <div className="flex flex-wrap gap-2 pt-1 font-mono text-[11px]">
                                  {dec.citedMetrics.map((cm, i) => (
                                    <div
                                      key={i}
                                      className="px-2 py-0.5 rounded bg-[#161616] border border-border-hairline flex items-center gap-1.5"
                                    >
                                      <span className="text-zinc-400">{cm.name}:</span>
                                      <span className="text-zinc-200 font-medium">{cm.citedValue}</span>
                                      <span className="text-purple-400 font-bold text-xs">✓</span>
                                    </div>
                                  ))}
                                </div>
                              )}
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )
      )}

      {/* Trade Forensic Autopsy Drawer */}
      <TradeAutopsyDrawer
        trade={autopsyPosition}
        onClose={() => setAutopsyPosition(null)}
      />
    </section>
  );
}
