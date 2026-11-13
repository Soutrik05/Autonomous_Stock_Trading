import { useState } from 'react';
import type { Position } from '../types';
import { formatPaiseToRupees, formatPct } from '../utils/formatters';

interface AssetAllocationTreemapProps {
  positions: Position[];
  cashPaise: number;
  totalNavPaise: number;
  onSelectPosition?: (pos: Position) => void;
}

export default function AssetAllocationTreemap({
  positions,
  cashPaise,
  totalNavPaise,
  onSelectPosition,
}: AssetAllocationTreemapProps) {
  const [viewMode, setViewMode] = useState<'STOCKS' | 'SECTORS'>('STOCKS');
  const [hoveredSymbol, setHoveredSymbol] = useState<string | null>(null);

  const activePositions = positions.filter((p) => p.status === 'OPEN');
  const effectiveTotalNav = totalNavPaise > 0 ? totalNavPaise : 50000000;

  // Compute stock weights
  const stockItems = activePositions.map((pos) => {
    const valuePaise = pos.quantity * pos.currentPricePaise;
    const weightPct = (valuePaise / effectiveTotalNav) * 100;
    return {
      pos,
      symbol: pos.symbol,
      name: pos.companyName || pos.symbol,
      sector: pos.sector || 'General',
      valuePaise,
      weightPct,
      pnlPct: pos.unrealizedPnlPct,
      pnlPaise: pos.unrealizedPnlPaise,
      shares: pos.quantity,
      entryPricePaise: pos.entryPricePaise,
      currentPricePaise: pos.currentPricePaise,
    };
  });

  // Cash weight
  const cashWeightPct = Math.max(0, (cashPaise / effectiveTotalNav) * 100);

  // Sort items by weight descending
  const sortedStocks = [...stockItems].sort((a, b) => b.weightPct - a.weightPct);

  // Group by sector for sector concentration view
  const sectorMap = new Map<string, { valuePaise: number; count: number; symbols: string[] }>();
  sortedStocks.forEach((item) => {
    const current = sectorMap.get(item.sector) || { valuePaise: 0, count: 0, symbols: [] };
    current.valuePaise += item.valuePaise;
    current.count += 1;
    current.symbols.push(item.symbol);
    sectorMap.set(item.sector, current);
  });

  // Add cash buffer as its own liquidity bucket
  if (cashPaise > 0) {
    sectorMap.set('Liquid Cash Reserve', {
      valuePaise: cashPaise,
      count: 0,
      symbols: ['INR_CASH'],
    });
  }

  const sectorList = Array.from(sectorMap.entries())
    .map(([sector, data]) => ({
      sector,
      valuePaise: data.valuePaise,
      weightPct: (data.valuePaise / effectiveTotalNav) * 100,
      count: data.count,
      symbols: data.symbols,
    }))
    .sort((a, b) => b.weightPct - a.weightPct);

  return (
    <div className="space-y-4 font-sans">
      {/* Header & View Mode Switcher */}
      <div className="flex items-center justify-between border-b border-white/[0.08] pb-3">
        <div>
          <h3 className="font-display text-lg font-medium text-white tracking-tight">
            Asset Allocation by Size
          </h3>
          <p className="text-xs font-mono text-zinc-400 mt-0.5">
            Proportional portfolio weighting & liquidity distribution
          </p>
        </div>

        {/* Toggle between Stock Treemap and Sector Mix */}
        <div className="flex items-center gap-1 p-0.5 rounded bg-[#181818] border border-white/10 text-xs font-mono">
          <button
            onClick={() => setViewMode('STOCKS')}
            className={`px-2.5 py-1 rounded transition-colors cursor-pointer text-xs ${
              viewMode === 'STOCKS'
                ? 'bg-white/[0.14] text-[#D4AF37] font-semibold border border-[#D4AF37]/40'
                : 'text-zinc-400 hover:text-white'
            }`}
          >
            Holdings Size
          </button>
          <button
            onClick={() => setViewMode('SECTORS')}
            className={`px-2.5 py-1 rounded transition-colors cursor-pointer text-xs ${
              viewMode === 'SECTORS'
                ? 'bg-white/[0.14] text-[#D4AF37] font-semibold border border-[#D4AF37]/40'
                : 'text-zinc-400 hover:text-white'
            }`}
          >
            Sector Mix
          </button>
        </div>
      </div>

      {/* VIEW 1: PROPORTIONAL HOLDINGS MOSAIC TILES (IMAGE 4 STYLE) */}
      {viewMode === 'STOCKS' ? (
        <div className="space-y-3">
          {/* Mosaic Visual Container */}
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
            {sortedStocks.map((stock) => {
              const isProfit = stock.pnlPct >= 0;
              const isHovered = hoveredSymbol === stock.symbol;

              return (
                <div
                  key={stock.symbol}
                  onMouseEnter={() => setHoveredSymbol(stock.symbol)}
                  onMouseLeave={() => setHoveredSymbol(null)}
                  onClick={() => onSelectPosition && onSelectPosition(stock.pos)}
                  style={{
                    minHeight: stock.weightPct > 20 ? '110px' : '95px',
                  }}
                  className={`p-3.5 rounded-sm border transition-all cursor-pointer flex flex-col justify-between ${
                    isProfit
                      ? 'bg-emerald-500/[0.04] border-emerald-500/20 hover:border-emerald-500/50 hover:bg-emerald-500/[0.08]'
                      : 'bg-[#c4553f]/[0.05] border-[#c4553f]/25 hover:border-[#c4553f]/50 hover:bg-[#c4553f]/[0.09]'
                  } ${isHovered ? 'scale-[1.02] shadow-xl' : ''}`}
                >
                  {/* Top Row: Symbol & Sector */}
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <span className="font-semibold text-white text-sm tracking-tight font-sans block">
                        {stock.symbol}
                      </span>
                      <span className="text-[10px] font-mono text-zinc-400 truncate block max-w-[120px]">
                        {stock.sector}
                      </span>
                    </div>
                    <span
                      className={`px-1.5 py-0.5 rounded text-[10px] font-mono font-medium ${
                        isProfit
                          ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                          : 'bg-[#c4553f]/15 text-[#c4553f] border border-[#c4553f]/30'
                      }`}
                    >
                      {isProfit ? `+${formatPct(stock.pnlPct)}` : formatPct(stock.pnlPct)}
                    </span>
                  </div>

                  {/* Bottom Row: Allocation Weight & Value */}
                  <div className="flex items-baseline justify-between gap-2 pt-2 border-t border-white/5 font-mono">
                    <span className="text-base font-bold text-white tabular-nums">
                      {stock.weightPct.toFixed(1)}%
                    </span>
                    <span className="text-[11px] text-zinc-400 tabular-nums">
                      {formatPaiseToRupees(stock.valuePaise)}
                    </span>
                  </div>
                </div>
              );
            })}

            {/* Liquid Cash Buffer Tile */}
            <div
              style={{ minHeight: '95px' }}
              className="p-3.5 rounded-sm border bg-[#D4AF37]/[0.04] border-[#D4AF37]/25 hover:border-[#D4AF37]/50 transition-all flex flex-col justify-between"
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <span className="font-semibold text-[#D4AF37] text-sm tracking-tight font-sans block">
                    Cash Reserve
                  </span>
                  <span className="text-[10px] font-mono text-zinc-400 block">
                    Unallocated Buffer
                  </span>
                </div>
                <span className="px-1.5 py-0.5 rounded text-[10px] font-mono font-medium bg-[#D4AF37]/15 text-[#D4AF37] border border-[#D4AF37]/30">
                  LIQUID
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
        </div>
      ) : (
        /* VIEW 2: SECTOR CONCENTRATION MIX */
        <div className="space-y-3">
          {/* Proportional Segmented Bar */}
          <div className="h-3 w-full rounded-sm overflow-hidden flex bg-zinc-900 border border-white/10">
            {sectorList.map((sec, i) => {
              const colors = [
                'bg-blue-500',
                'bg-emerald-500',
                'bg-amber-500',
                'bg-purple-500',
                'bg-rose-500',
                'bg-cyan-500',
              ];
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

          {/* Sector Breakdown Rows */}
          <div className="space-y-1.5 font-mono text-xs">
            {sectorList.map((sec, i) => {
              const colors = [
                'bg-blue-400',
                'bg-emerald-400',
                'bg-amber-400',
                'bg-purple-400',
                'bg-rose-400',
                'bg-cyan-400',
              ];
              const dotColor = sec.sector.includes('Cash') ? 'bg-[#D4AF37]' : colors[i % colors.length];

              return (
                <div
                  key={sec.sector}
                  className="flex items-center justify-between p-2 rounded-sm bg-white/[0.02] border border-white/5 hover:border-white/15 transition-colors"
                >
                  <div className="flex items-center gap-2">
                    <span className={`w-2 h-2 rounded-full ${dotColor}`} />
                    <span className="text-zinc-200 font-medium font-sans text-xs">
                      {sec.sector}
                    </span>
                    {sec.count > 0 && (
                      <span className="text-[10px] text-zinc-500 font-mono">
                        ({sec.count} {sec.count === 1 ? 'stock' : 'stocks'})
                      </span>
                    )}
                  </div>

                  <div className="flex items-center gap-4 tabular-nums">
                    <span className="text-zinc-400 text-xs">
                      {formatPaiseToRupees(sec.valuePaise)}
                    </span>
                    <span className="font-bold text-white text-xs w-12 text-right">
                      {sec.weightPct.toFixed(1)}%
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* QUICK EXPOSURE BREAKDOWN TABLE (IMAGE 4 STYLE) */}
      <div className="pt-2 border-t border-white/[0.08]">
        <div className="overflow-x-auto">
          <table className="w-full text-left font-mono text-xs border-collapse">
            <thead>
              <tr className="border-b border-white/10 text-[10px] text-zinc-400 font-sans uppercase tracking-wider">
                <th className="py-2 px-2 font-medium">Asset</th>
                <th className="py-2 px-3 text-right font-medium">Shares</th>
                <th className="py-2 px-3 text-right font-medium">Weight</th>
                <th className="py-2 px-3 text-right font-medium">Value</th>
                <th className="py-2 px-2 text-right font-medium">P&L</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5 text-[11px]">
              {sortedStocks.map((s) => (
                <tr key={s.symbol} className="hover:bg-white/[0.03] transition-colors">
                  <td className="py-2 px-2 font-sans font-medium text-white flex items-center gap-1.5">
                    <span>{s.symbol}</span>
                    <span className="text-[9px] font-mono text-zinc-500">· {s.sector}</span>
                  </td>
                  <td className="py-2 px-3 text-right text-zinc-300 tabular-nums">
                    {s.shares}
                  </td>
                  <td className="py-2 px-3 text-right font-semibold text-white tabular-nums">
                    {s.weightPct.toFixed(1)}%
                  </td>
                  <td className="py-2 px-3 text-right text-zinc-300 tabular-nums">
                    {formatPaiseToRupees(s.valuePaise)}
                  </td>
                  <td
                    className={`py-2 px-2 text-right font-semibold tabular-nums ${
                      s.pnlPct >= 0 ? 'text-emerald-400' : 'text-[#c4553f]'
                    }`}
                  >
                    {s.pnlPct >= 0 ? `+${formatPct(s.pnlPct)}` : formatPct(s.pnlPct)}
                  </td>
                </tr>
              ))}
              {/* Cash Buffer Line */}
              <tr className="bg-[#D4AF37]/[0.02]">
                <td className="py-2 px-2 font-sans font-medium text-[#D4AF37]">
                  Liquid Cash
                </td>
                <td className="py-2 px-3 text-right text-zinc-500 tabular-nums">-</td>
                <td className="py-2 px-3 text-right font-semibold text-[#D4AF37] tabular-nums">
                  {cashWeightPct.toFixed(1)}%
                </td>
                <td className="py-2 px-3 text-right text-zinc-300 tabular-nums">
                  {formatPaiseToRupees(cashPaise)}
                </td>
                <td className="py-2 px-2 text-right text-zinc-500 tabular-nums">-</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

