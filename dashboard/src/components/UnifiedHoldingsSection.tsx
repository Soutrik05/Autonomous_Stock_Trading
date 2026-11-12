import { useState } from 'react';
import type { Position } from '../types';
import { formatPaiseToRupees, formatPct } from '../utils/formatters';

interface UnifiedHoldingsSectionProps {
  positions: Position[];
  cashPaise: number;
  totalNavPaise: number;
}

export default function UnifiedHoldingsSection({
  positions,
  cashPaise,
  totalNavPaise,
}: UnifiedHoldingsSectionProps) {
  const [allocationMode, setAllocationMode] = useState<'STOCKS' | 'SECTORS'>('STOCKS');
  const [hoveredSymbol, setHoveredSymbol] = useState<string | null>(null);

  const activePositions = positions.filter((p) => p.status === 'OPEN');
  const effectiveNav = totalNavPaise > 0 ? totalNavPaise : 50000000;

  // Calculate allocation metrics
  const holdings = activePositions.map((p) => {
    const currentValuePaise = p.quantity * p.currentPricePaise;
    const weightPct = (currentValuePaise / effectiveNav) * 100;
    return {
      pos: p,
      symbol: p.symbol,
      company: p.companyName || p.symbol,
      sector: p.sector || 'General',
      shares: p.quantity,
      entryPricePaise: p.entryPricePaise,
      currentPricePaise: p.currentPricePaise,
      currentValuePaise,
      weightPct,
      pnlPaise: p.unrealizedPnlPaise,
      pnlPct: p.unrealizedPnlPct,
      stopLossPaise: p.stopLossPaise,
      targetPricePaise: p.targetPricePaise,
      holdDays: p.holdDays ?? 0,
    };
  });

  const cashWeightPct = Math.max(0, (cashPaise / effectiveNav) * 100);
  const sortedHoldings = [...holdings].sort((a, b) => b.weightPct - a.weightPct);

  // Group by sector for sector concentration mode
  const sectorMap = new Map<string, { valuePaise: number; count: number }>();
  sortedHoldings.forEach((h) => {
    const curr = sectorMap.get(h.sector) || { valuePaise: 0, count: 0 };
    curr.valuePaise += h.currentValuePaise;
    curr.count += 1;
    sectorMap.set(h.sector, curr);
  });
  if (cashPaise > 0) {
    sectorMap.set('Liquid Cash Reserve', { valuePaise: cashPaise, count: 0 });
  }
  const sectorList = Array.from(sectorMap.entries())
    .map(([sector, data]) => ({
      sector,
      valuePaise: data.valuePaise,
      weightPct: (data.valuePaise / effectiveNav) * 100,
      count: data.count,
    }))
    .sort((a, b) => b.weightPct - a.weightPct);

  return (
    <section className="space-y-4 font-sans">
      {/* Section Header with Allocation Mode Switcher */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 border-b border-white/[0.08] pb-3">
        <div>
          <h2 className="font-display text-2xl font-normal tracking-tight text-white flex items-center gap-2.5">
            <span>Active Holdings & Capital Allocation</span>
            <span className="text-xs font-mono px-2 py-0.5 rounded bg-white/[0.04] text-zinc-400 border border-white/10 font-normal">
              {activePositions.length} {activePositions.length === 1 ? 'Position' : 'Positions'}
            </span>
          </h2>
          <p className="text-xs font-mono text-zinc-400 mt-0.5">
            Proportional capital deployment, excursion limits & unrealized returns
          </p>
        </div>

        {/* Allocation Mode Switcher */}
        <div className="flex items-center gap-1 p-0.5 rounded bg-[#181818] border border-white/10 text-xs font-mono">
          <button
            onClick={() => setAllocationMode('STOCKS')}
            className={`px-3 py-1 rounded transition-colors cursor-pointer text-xs ${
              allocationMode === 'STOCKS'
                ? 'bg-white/[0.14] text-[#D4AF37] font-semibold border border-[#D4AF37]/40'
                : 'text-zinc-400 hover:text-white'
            }`}
          >
            Position Weights
          </button>
          <button
            onClick={() => setAllocationMode('SECTORS')}
            className={`px-3 py-1 rounded transition-colors cursor-pointer text-xs ${
              allocationMode === 'SECTORS'
                ? 'bg-white/[0.14] text-[#D4AF37] font-semibold border border-[#D4AF37]/40'
                : 'text-zinc-400 hover:text-white'
            }`}
          >
            Sector Concentration
          </button>
        </div>
      </div>

      {/* 1. VISUAL PROPORTIONAL ALLOCATION MOSAIC (IMAGE 4 STYLE) */}
      {allocationMode === 'STOCKS' ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
          {sortedHoldings.map((item) => {
            const isProfit = item.pnlPct >= 0;
            const isHovered = hoveredSymbol === item.symbol;

            return (
              <div
                key={item.symbol}
                onMouseEnter={() => setHoveredSymbol(item.symbol)}
                onMouseLeave={() => setHoveredSymbol(null)}
                className={`p-3.5 rounded-sm border transition-all flex flex-col justify-between ${
                  isProfit
                    ? 'bg-emerald-500/[0.04] border-emerald-500/20 hover:border-emerald-500/50 hover:bg-emerald-500/[0.08]'
                    : 'bg-[#c4553f]/[0.05] border-[#c4553f]/25 hover:border-[#c4553f]/50 hover:bg-[#c4553f]/[0.09]'
                } ${isHovered ? 'scale-[1.02] shadow-xl' : ''}`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <span className="font-semibold text-white text-sm tracking-tight font-sans block">
                      {item.symbol}
                    </span>
                    <span className="text-[10px] font-mono text-zinc-400 truncate block max-w-[130px]">
                      {item.sector}
                    </span>
                  </div>
                  <span
                    className={`px-1.5 py-0.5 rounded text-[10px] font-mono font-medium ${
                      isProfit
                        ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                        : 'bg-[#c4553f]/15 text-[#c4553f] border border-[#c4553f]/30'
                    }`}
                  >
                    {isProfit ? `+${formatPct(item.pnlPct)}` : formatPct(item.pnlPct)}
                  </span>
                </div>

                <div className="flex items-baseline justify-between gap-2 pt-2 border-t border-white/5 font-mono">
                  <span className="text-base font-bold text-white tabular-nums">
                    {item.weightPct.toFixed(1)}%
                  </span>
                  <span className="text-[11px] text-zinc-400 tabular-nums">
                    {formatPaiseToRupees(item.currentValuePaise)}
                  </span>
                </div>
              </div>
            );
          })}

          {/* Liquid Cash Buffer Tile */}
          <div className="p-3.5 rounded-sm border bg-[#D4AF37]/[0.04] border-[#D4AF37]/25 hover:border-[#D4AF37]/50 transition-all flex flex-col justify-between">
            <div className="flex items-start justify-between gap-2">
              <div>
                <span className="font-semibold text-[#D4AF37] text-sm tracking-tight font-sans block">
                  Liquid Cash
                </span>
                <span className="text-[10px] font-mono text-zinc-400 block">
                  Unallocated Reserve
                </span>
              </div>
              <span className="px-1.5 py-0.5 rounded text-[10px] font-mono font-medium bg-[#D4AF37]/15 text-[#D4AF37] border border-[#D4AF37]/30">
                BUFFER
              </span>
            </div>

            <div className="flex items-baseline justify-between gap-2 pt-2 border-t border-[#D4AF37]/10 font-mono">
              <span className="text-base font-bold text-zinc-100 tabular-nums">
                {cashWeightPct.toFixed(1)}%
              </span>
              <span className="text-[11px] text-[#D4AF37] tabular-nums font-medium">
                {formatPaiseToRupees(cashPaise)}
              </span>
            </div>
          </div>
        </div>
      ) : (
        /* Sector Concentration Mode */
        <div className="space-y-3 bg-[#181818] border border-white/[0.08] p-4 rounded-sm">
          {/* Segmented bar */}
          <div className="h-3 w-full rounded-sm overflow-hidden flex bg-zinc-900 border border-white/10">
            {sectorList.map((sec, i) => {
              const colors = ['bg-blue-500', 'bg-emerald-500', 'bg-amber-500', 'bg-purple-500', 'bg-rose-500'];
              const c = sec.sector.includes('Cash') ? 'bg-[#D4AF37]' : colors[i % colors.length];
              return (
                <div
                  key={sec.sector}
                  style={{ width: `${Math.max(1, sec.weightPct)}%` }}
                  title={`${sec.sector}: ${sec.weightPct.toFixed(1)}%`}
                  className={`${c} h-full transition-all`}
                />
              );
            })}
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2 text-xs font-mono">
            {sectorList.map((sec, i) => {
              const colors = ['bg-blue-400', 'bg-emerald-400', 'bg-amber-400', 'bg-purple-400', 'bg-rose-400'];
              const dot = sec.sector.includes('Cash') ? 'bg-[#D4AF37]' : colors[i % colors.length];
              return (
                <div
                  key={sec.sector}
                  className="flex items-center justify-between p-2 rounded-sm bg-white/[0.02] border border-white/5"
                >
                  <div className="flex items-center gap-2">
                    <span className={`w-2 h-2 rounded-full ${dot}`} />
                    <span className="text-zinc-200 font-sans text-xs">{sec.sector}</span>
                  </div>
                  <span className="font-semibold text-white">{sec.weightPct.toFixed(1)}%</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 2. COMPREHENSIVE HOLDINGS TABLE (SINGLE UNIFIED TABLE, NO DUPLICATION) */}
      <div className="border border-white/[0.08] overflow-hidden bg-[#1E1E1E]">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono text-zinc-300 border-collapse">
            <thead className="bg-white/[0.02] text-[11px] text-zinc-400 border-b border-white/10 uppercase tracking-wider font-sans">
              <tr>
                <th className="py-3 px-4 font-medium min-w-[200px]">Security / Sector</th>
                <th className="py-3 px-3 text-right font-medium">Qty</th>
                <th className="py-3 px-4 text-right font-medium">Entry Price</th>
                <th className="py-3 px-4 text-right font-medium">Current LTP</th>
                <th className="py-3 px-4 text-right font-medium">Position Value</th>
                <th className="py-3 px-3 text-right font-medium">Weight</th>
                <th className="py-3 px-4 text-right font-medium">Stop Loss</th>
                <th className="py-3 px-4 text-right font-medium">Target Price</th>
                <th className="py-3 px-4 text-right font-medium">Unrealized P&L</th>
              </tr>
            </thead>

            <tbody className="divide-y divide-white/5">
              {sortedHoldings.length === 0 ? (
                <tr>
                  <td colSpan={9} className="py-8 text-center text-zinc-500 font-mono">
                    No active positions currently open. Portfolio is 100% in liquid cash reserve.
                  </td>
                </tr>
              ) : (
                sortedHoldings.map((h) => {
                  const isProfit = h.pnlPct >= 0;
                  const isHovered = hoveredSymbol === h.symbol;

                  return (
                    <tr
                      key={h.symbol}
                      onMouseEnter={() => setHoveredSymbol(h.symbol)}
                      onMouseLeave={() => setHoveredSymbol(null)}
                      className={`hover:bg-white/[0.035] transition-colors ${
                        isHovered ? 'bg-white/[0.02]' : ''
                      }`}
                    >
                      {/* Symbol & Company Name */}
                      <td className="py-3.5 px-4 font-sans">
                        <div className="font-semibold text-white text-sm tracking-tight">
                          {h.symbol}
                        </div>
                        <div className="text-[11px] font-mono text-zinc-400 mt-0.5">
                          {h.company} · {h.sector}
                        </div>
                      </td>

                      {/* Shares */}
                      <td className="py-3.5 px-3 text-right tabular-nums text-white font-medium">
                        {h.shares}
                      </td>

                      {/* Entry Price */}
                      <td className="py-3.5 px-4 text-right tabular-nums text-zinc-300">
                        {formatPaiseToRupees(h.entryPricePaise)}
                      </td>

                      {/* Current LTP */}
                      <td className="py-3.5 px-4 text-right tabular-nums text-white font-semibold">
                        {formatPaiseToRupees(h.currentPricePaise)}
                      </td>

                      {/* Position Value */}
                      <td className="py-3.5 px-4 text-right tabular-nums text-zinc-200">
                        {formatPaiseToRupees(h.currentValuePaise)}
                      </td>

                      {/* Weight % */}
                      <td className="py-3.5 px-3 text-right tabular-nums text-white font-bold">
                        {h.weightPct.toFixed(1)}%
                      </td>

                      {/* Stop Loss */}
                      <td className="py-3.5 px-4 text-right tabular-nums text-zinc-400">
                        {h.stopLossPaise ? formatPaiseToRupees(h.stopLossPaise) : '—'}
                      </td>

                      {/* Target Price */}
                      <td className="py-3.5 px-4 text-right tabular-nums text-zinc-400">
                        {h.targetPricePaise ? formatPaiseToRupees(h.targetPricePaise) : '—'}
                      </td>

                      {/* Unrealized P&L */}
                      <td className="py-3.5 px-4 text-right tabular-nums">
                        <span
                          className={`font-semibold ${
                            isProfit ? 'text-emerald-400' : 'text-[#c4553f]'
                          }`}
                        >
                          {isProfit ? `+${formatPaiseToRupees(h.pnlPaise)}` : formatPaiseToRupees(h.pnlPaise)}
                          {' '}
                          <span className="text-[11px]">
                            ({isProfit ? `+${formatPct(h.pnlPct)}` : formatPct(h.pnlPct)})
                          </span>
                        </span>
                      </td>
                    </tr>
                  );
                })
              )}

              {/* Cash Reserve Row */}
              <tr className="bg-[#D4AF37]/[0.02]">
                <td className="py-3.5 px-4 font-sans">
                  <div className="font-semibold text-[#D4AF37] text-sm">Liquid Cash Buffer</div>
                  <div className="text-[11px] font-mono text-zinc-500 mt-0.5">
                    Unallocated Trading Capital
                  </div>
                </td>
                <td className="py-3.5 px-3 text-right text-zinc-500 tabular-nums">—</td>
                <td className="py-3.5 px-4 text-right text-zinc-500 tabular-nums">—</td>
                <td className="py-3.5 px-4 text-right text-zinc-500 tabular-nums">—</td>
                <td className="py-3.5 px-4 text-right tabular-nums text-[#D4AF37] font-semibold">
                  {formatPaiseToRupees(cashPaise)}
                </td>
                <td className="py-3.5 px-3 text-right tabular-nums text-[#D4AF37] font-bold">
                  {cashWeightPct.toFixed(1)}%
                </td>
                <td className="py-3.5 px-4 text-right text-zinc-500 tabular-nums">—</td>
                <td className="py-3.5 px-4 text-right text-zinc-500 tabular-nums">—</td>
                <td className="py-3.5 px-4 text-right text-zinc-500 tabular-nums font-mono">
                  PAR
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

