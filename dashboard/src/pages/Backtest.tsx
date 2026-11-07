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
      <div className="max-w-7xl mx-auto px-4 py-24 flex justify-center items-center">
        <div className="flex items-center gap-3 text-slate-400 font-mono text-sm">
          <div className="w-5 h-5 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />
          <span>Loading historical walk-forward backtest data...</span>
        </div>
      </div>
    );
  }

  const activeWindow = windows.find((w) => w.windowId === selectedWindowId) || windows[0];

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8 animate-fade-in font-sans">
      {/* Header */}
      <div className="border-b border-white/10 pb-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-mono text-purple-400 flex items-center gap-1.5 font-medium">
              <History className="w-4 h-4" />
              <span>Walk-Forward Historical Evaluation</span>
            </span>
            <BacktestDerivedBadge size="sm" />
          </div>
          <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-white">
            Historical Walk-Forward Backtesting Lab
          </h1>
          <p className="text-sm text-slate-400 mt-1 max-w-3xl leading-relaxed">
            Multi-regime 180-day rolling simulation windows with isolated state storage and persistent inference caching. Validates complete holding cycles for long-horizon personas (Jhunjhunwala 90–180d, Lynch 60–120d).
          </p>
        </div>

        {/* Evidence Isolation Notice */}
        <div className="arena-glass-subdued px-4 py-2.5 text-xs font-mono max-w-xs border-purple-500/30 text-purple-300">
          <strong>Strict Isolation Guardrail:</strong> Evaluated against daily OHLCV bands and permanently isolated from live pilot records.
        </div>
      </div>

      {/* Regime Window Switcher Tabs */}
      <div className="flex flex-wrap gap-4">
        {windows.map((win) => {
          const isSelected = win.windowId === activeWindow.windowId;
          const isBull = win.marketRegime === 'BULL';
          return (
            <button
              key={win.windowId}
              onClick={() => setSelectedWindowId(win.windowId)}
              className={`p-5 rounded-xl border text-left transition-all cursor-pointer flex-1 min-w-[280px] ${
                isSelected
                  ? 'border-cyan-500/50 bg-cyan-500/10 shadow-[0_0_25px_rgba(6,182,212,0.15)]'
                  : 'border-white/10 bg-white/[0.02] hover:bg-white/[0.05]'
              }`}
            >
              <div className="flex justify-between items-center mb-1.5">
                <span className="font-mono text-xs text-slate-400">
                  {win.startDate} → {win.endDate}
                </span>
                <span
                  className={`text-[10px] font-mono px-2 py-0.5 rounded border font-medium ${
                    isBull ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' : 'bg-amber-500/15 text-amber-400 border-amber-500/30'
                  }`}
                >
                  {win.marketRegime} REGIME
                </span>
              </div>
              <div className="font-bold text-white text-base mt-1">
                {win.name}
              </div>
              <div className="text-xs text-slate-400 mt-2 font-mono flex items-center gap-1.5">
                <span>Nifty 500 Index:</span>
                <strong className={win.nifty500ReturnPct >= 0 ? 'text-emerald-400' : 'text-rose-400'}>
                  {formatPct(win.nifty500ReturnPct)}
                </strong>
              </div>
            </button>
          );
        })}
      </div>

      {/* Empirical Holding Duration Table */}
      <div className="arena-glass p-6 sm:p-7 space-y-4 shadow-2xl">
        <div>
          <div className="flex items-center gap-2.5">
            <h3 className="text-base sm:text-lg font-bold text-white">
              Empirical Holding Duration & Thesis Resolution
            </h3>
            <BacktestDerivedBadge size="sm" />
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Empirical verification that agent holding theses have completed full cycles, validating that the weekly heuristic reflection loop exercises over historical calendar spans.
          </p>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono text-slate-200">
            <thead className="bg-white/[0.02] text-[11px] text-slate-400 border-b border-white/10">
              <tr>
                <th className="py-3 px-4 font-semibold">Agent Persona</th>
                <th className="py-3 px-4 text-center font-semibold">Intended Horizon</th>
                <th className="py-3 px-4 text-center font-semibold">Empirical Avg Hold</th>
                <th className="py-3 px-4 text-center font-semibold">Max Hold Observed</th>
                <th className="py-3 px-4 text-center font-semibold">Resolved Full Cycles</th>
                <th className="py-3 px-4 text-center font-semibold">Cycle Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {activeWindow.resolvedDurations.map((dur) => (
                <tr key={dur.agentId} className="hover:bg-white/[0.04] transition-colors">
                  <td className="py-3.5 px-4 font-semibold text-white">{dur.agentName}</td>
                  <td className="py-3.5 px-4 text-center text-slate-400">{dur.intendedHorizonDays}</td>
                  <td className="py-3.5 px-4 text-center font-bold text-amber-300">
                    {dur.empiricalAvgHoldDays.toFixed(1)} days
                  </td>
                  <td className="py-3.5 px-4 text-center text-slate-400">{dur.maxHoldDays} days</td>
                  <td className="py-3.5 px-4 text-center font-bold text-purple-300">
                    {dur.resolvedCyclesCount} cycles
                  </td>
                  <td className="py-3.5 px-4 text-center">
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                      Resolved (&gt;1 full cycle)
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Historical Simulation Performance Table for Selected Window */}
      <div className="arena-glass overflow-hidden shadow-2xl">
        <div className="p-5 border-b border-white/10 flex justify-between items-center bg-white/[0.02]">
          <div>
            <div className="flex items-center gap-2.5">
              <h3 className="text-base font-bold text-white">
                Backtest Results: {activeWindow.name}
              </h3>
              <BacktestDerivedBadge size="sm" />
            </div>
            <p className="text-xs text-slate-400">
              Calculated against daily OHLCV bands with full statutory charges applied at entry and exit.
            </p>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono text-slate-200">
            <thead className="bg-white/[0.02] text-[11px] text-slate-400 border-b border-white/10">
              <tr>
                <th className="py-3 px-4 font-semibold">Agent</th>
                <th className="py-3 px-4 text-right font-semibold">Final NAV (₹)</th>
                <th className="py-3 px-4 text-right font-semibold">Return</th>
                <th className="py-3 px-4 text-right font-semibold">Alpha vs N500</th>
                <th className="py-3 px-4 text-right font-semibold">Sharpe</th>
                <th className="py-3 px-4 text-right font-semibold">Max DD</th>
                <th className="py-3 px-4 text-right font-semibold">Win Rate</th>
                <th className="py-3 px-4 text-right font-semibold">Faithfulness</th>
                <th className="py-3 px-4 text-center font-semibold">Closed Trades</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {activeWindow.agents.map((ag) => (
                <tr key={ag.id} className="hover:bg-white/[0.04] transition-colors">
                  <td className="py-3.5 px-4 font-semibold text-white">{ag.name}</td>
                  <td className="py-3.5 px-4 text-right font-medium text-white">{formatPaiseToRupees(ag.navPaise)}</td>
                  <td className={`py-3.5 px-4 text-right font-bold ${ag.returnPct >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                    {formatPct(ag.returnPct)}
                  </td>
                  <td className={`py-3.5 px-4 text-right font-semibold ${ag.alphaVsBenchmarkPct >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                    {ag.alphaVsBenchmarkPct >= 0 ? `+${formatPct(ag.alphaVsBenchmarkPct)}` : formatPct(ag.alphaVsBenchmarkPct)}
                  </td>
                  <td className="py-3.5 px-4 text-right text-slate-300">{ag.sharpeRatio.toFixed(2)}</td>
                  <td className="py-3.5 px-4 text-right text-rose-400">-{ag.maxDrawdownPct.toFixed(2)}%</td>
                  <td className="py-3.5 px-4 text-right text-slate-300">{ag.winRatePct.toFixed(1)}%</td>
                  <td className="py-3.5 px-4 text-right text-purple-400 font-semibold">{ag.faithfulnessRatePct.toFixed(1)}%</td>
                  <td className="py-3.5 px-4 text-center text-slate-400">{ag.closedTrades}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
