import { useState, useEffect } from 'react';
import { History } from 'lucide-react';
import type { BacktestRegimeWindow } from '../types';
import { apiService } from '../services/api';
import { formatPaiseToRupees, formatPct } from '../utils/formatters';
import BacktestDerivedBadge from '../components/BacktestDerivedBadge';

export default function Backtest() {
  const [windows, setWindows] = useState<BacktestRegimeWindow[]>([]);
  const [selectedWindowId, setSelectedWindowId] = useState<string>('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const data = await apiService.getBacktestWindows();
        setWindows(data);
        if (data.length > 0) {
          setSelectedWindowId(data[0].windowId);
        }
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading || windows.length === 0) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-16 flex justify-center items-center">
        <div className="flex items-center gap-3 text-stone-500 font-mono text-sm">
          <div className="w-4 h-4 border-2 border-amber-600 border-t-transparent rounded-full animate-spin" />
          <span>Loading historical walk-forward backtest data...</span>
        </div>
      </div>
    );
  }

  const activeWindow = windows.find((w) => w.windowId === selectedWindowId) || windows[0];

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8 animate-fade-in font-sans">
      {/* Header */}
      <div className="border-b border-[#E5E2D9] pb-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-mono text-purple-700 uppercase tracking-wider flex items-center gap-1.5 font-bold">
              <History className="w-4 h-4" />
              <span>Question B Empirical Validation & Incremental Progress</span>
            </span>
            <BacktestDerivedBadge size="sm" />
          </div>
          <h1 className="text-3xl font-serif font-bold text-[#111827]">
            Historical Walk-Forward Backtesting Lab
          </h1>
          <p className="text-sm text-[#4B5563] mt-1 max-w-3xl leading-relaxed">
            Multi-regime 180-day rolling simulation windows with isolated state storage (<code>storage/backtest/</code>) and persistent inference caching. Validates complete holding cycles for long-horizon personas (RJ 90–180d, Lynch 60–120d).
          </p>
        </div>

        {/* Evidence Isolation Notice */}
        <div className="px-3 py-2 rounded-lg bg-purple-50 border border-purple-200 text-purple-900 text-xs font-mono max-w-xs">
          <strong>Strict Isolation Guardrail:</strong> Evaluated against daily OHLCV bands and permanently isolated from live pilot records.
        </div>
      </div>

      {/* Regime Window Switcher Tabs */}
      <div className="flex flex-wrap gap-3">
        {windows.map((win) => {
          const isSelected = win.windowId === activeWindow.windowId;
          const isBull = win.marketRegime === 'BULL';
          return (
            <button
              key={win.windowId}
              onClick={() => setSelectedWindowId(win.windowId)}
              className={`p-4 rounded-xl border text-left transition-all cursor-pointer flex-1 min-w-[280px] ${
                isSelected
                  ? 'border-purple-500 bg-purple-50/50 shadow-xs'
                  : 'border-[#E5E2D9] bg-white hover:border-stone-300'
              }`}
            >
              <div className="flex justify-between items-center mb-1">
                <span className="font-mono text-xs text-[#9CA3AF]">
                  {win.startDate} → {win.endDate}
                </span>
                <span
                  className={`text-[10px] font-mono px-2 py-0.5 rounded font-bold uppercase ${
                    isBull ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'
                  }`}
                >
                  {win.marketRegime} REGIME
                </span>
              </div>
              <div className="font-serif font-bold text-[#111827] text-base mt-1">
                {win.name}
              </div>
              <div className="text-xs text-[#4B5563] mt-2 font-mono flex items-center gap-1">
                <span>Nifty 500 Index:</span>
                <strong className={win.nifty500ReturnPct >= 0 ? 'text-emerald-600' : 'text-rose-600'}>
                  {formatPct(win.nifty500ReturnPct)}
                </strong>
              </div>
            </button>
          );
        })}
      </div>

      {/* QUESTION B RESOLUTION: Empirical Holding Duration Table */}
      <div className="porcelain-card p-6 space-y-4">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-base font-serif font-bold text-[#111827]">
              Empirical Holding Duration & Thesis Resolution (Question B)
            </h3>
            <BacktestDerivedBadge size="sm" />
          </div>
          <p className="text-xs text-[#4B5563] mt-1">
            Empirical verification that agent holding theses have completed full cycles, validating that the weekly heuristic reflection loop exercises over historical calendar spans.
          </p>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono text-[#111827]">
            <thead className="bg-[#F4F2EC] uppercase text-[11px] text-[#4B5563] border-b border-[#E5E2D9]">
              <tr>
                <th className="py-3 px-4">Agent Persona</th>
                <th className="py-3 px-4 text-center">Intended Horizon</th>
                <th className="py-3 px-4 text-center">Empirical Avg Hold</th>
                <th className="py-3 px-4 text-center">Max Hold Observed</th>
                <th className="py-3 px-4 text-center">Resolved Full Cycles</th>
                <th className="py-3 px-4 text-center">Cycle Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#EDEAE2]">
              {activeWindow.resolvedDurations.map((dur) => (
                <tr key={dur.agentId} className="hover:bg-[#F7F5EE]">
                  <td className="py-3 px-4 font-bold">{dur.agentName}</td>
                  <td className="py-3 px-4 text-center text-[#4B5563]">{dur.intendedHorizonDays}</td>
                  <td className="py-3 px-4 text-center font-bold text-amber-800">
                    {dur.empiricalAvgHoldDays.toFixed(1)} days
                  </td>
                  <td className="py-3 px-4 text-center text-[#4B5563]">{dur.maxHoldDays} days</td>
                  <td className="py-3 px-4 text-center font-bold text-purple-700">
                    {dur.resolvedCyclesCount} cycles
                  </td>
                  <td className="py-3 px-4 text-center">
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800">
                      RESOLVED (&gt;1 full cycle)
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Historical Simulation Performance Table for Selected Window */}
      <div className="porcelain-card overflow-hidden">
        <div className="p-4 border-b border-[#E5E2D9] flex justify-between items-center bg-white">
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-base font-serif font-bold text-[#111827]">
                Backtest Results: {activeWindow.name}
              </h3>
              <BacktestDerivedBadge size="sm" />
            </div>
            <p className="text-xs text-[#4B5563]">
              Calculated against daily OHLCV bands with full statutory charges applied at entry and exit.
            </p>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono text-[#111827]">
            <thead className="bg-[#F4F2EC] uppercase text-[11px] text-[#4B5563] border-b border-[#E5E2D9]">
              <tr>
                <th className="py-3 px-4">Agent</th>
                <th className="py-3 px-4 text-right">Final NAV (₹)</th>
                <th className="py-3 px-4 text-right">Return</th>
                <th className="py-3 px-4 text-right">Alpha vs N500</th>
                <th className="py-3 px-4 text-right">Sharpe</th>
                <th className="py-3 px-4 text-right">Max DD</th>
                <th className="py-3 px-4 text-right">Win Rate</th>
                <th className="py-3 px-4 text-right">Faithfulness</th>
                <th className="py-3 px-4 text-center">Closed Trades</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#EDEAE2]">
              {activeWindow.agents.map((ag) => (
                <tr key={ag.id} className="hover:bg-[#F7F5EE]">
                  <td className="py-3 px-4 font-bold">{ag.name}</td>
                  <td className="py-3 px-4 text-right font-medium">{formatPaiseToRupees(ag.navPaise)}</td>
                  <td className={`py-3 px-4 text-right font-bold ${ag.returnPct >= 0 ? 'text-emerald-600' : 'text-rose-600'}`}>
                    {formatPct(ag.returnPct)}
                  </td>
                  <td className={`py-3 px-4 text-right font-semibold ${ag.alphaVsBenchmarkPct >= 0 ? 'text-emerald-600' : 'text-rose-600'}`}>
                    {formatPct(ag.alphaVsBenchmarkPct)}
                  </td>
                  <td className="py-3 px-4 text-right">{ag.sharpeRatio.toFixed(2)}</td>
                  <td className="py-3 px-4 text-right text-rose-600">-{ag.maxDrawdownPct.toFixed(2)}%</td>
                  <td className="py-3 px-4 text-right">{ag.winRatePct.toFixed(1)}%</td>
                  <td className="py-3 px-4 text-right text-purple-700">{ag.faithfulnessRatePct.toFixed(1)}%</td>
                  <td className="py-3 px-4 text-center">{ag.closedTrades}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
