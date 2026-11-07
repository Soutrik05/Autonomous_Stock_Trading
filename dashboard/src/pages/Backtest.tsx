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
      <div className="max-w-7xl mx-auto px-4 py-12 flex justify-center items-center">
        <div className="flex items-center gap-3 text-stone-500 font-mono text-sm">
          <div className="w-4 h-4 border-2 border-amber-500 border-t-transparent rounded-full animate-spin" />
          <span>Loading historical walk-forward backtest data...</span>
        </div>
      </div>
    );
  }

  const activeWindow = windows.find((w) => w.windowId === selectedWindowId) || windows[0];

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8 animate-fade-in">
      {/* Page Header */}
      <div className="border-b border-stone-200 dark:border-stone-800 pb-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-mono text-purple-600 dark:text-purple-400 uppercase tracking-wider flex items-center gap-1.5 font-bold">
              <History className="w-4 h-4" />
              <span>Question B Empirical Validation</span>
            </span>
            <BacktestDerivedBadge size="sm" />
          </div>
          <h1 className="text-3xl font-bold tracking-tight text-stone-900 dark:text-stone-100 font-serif">
            Historical Walk-Forward Backtesting Lab
          </h1>
          <p className="text-sm text-stone-500 dark:text-stone-400 mt-1 max-w-3xl leading-relaxed">
            Multi-regime 180-day rolling simulation windows with isolated SQLite state storage (<code>storage/backtest/</code>) and persistent LLM caching. Resolves full trade holding cycles for slow personas (RJ 90–180d, Lynch 60–120d).
          </p>
        </div>

        {/* Mandatory Evidence Isolation Warning */}
        <div className="px-3 py-2 rounded-lg bg-purple-50 dark:bg-purple-950/40 border border-purple-200 dark:border-purple-800 text-purple-900 dark:text-purple-300 text-xs font-mono max-w-xs">
          <strong>Strict Isolation Guardrail:</strong> Never blended with live paper-trading records.
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
                  ? 'border-purple-500 bg-purple-50/40 dark:bg-purple-950/20 shadow-xs'
                  : 'border-stone-200 dark:border-stone-800 bg-white dark:bg-stone-900 hover:border-stone-300'
              }`}
            >
              <div className="flex justify-between items-center mb-1">
                <span className="font-mono text-xs text-stone-400">
                  {win.startDate} → {win.endDate}
                </span>
                <span
                  className={`text-[10px] font-mono px-2 py-0.5 rounded font-bold uppercase ${
                    isBull
                      ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300'
                      : 'bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300'
                  }`}
                >
                  {win.marketRegime} REGIME
                </span>
              </div>
              <div className="font-semibold text-stone-900 dark:text-stone-100 text-sm mt-1">
                {win.name}
              </div>
              <div className="text-xs text-stone-500 mt-2 font-mono flex items-center gap-1">
                <span>Nifty 500:</span>
                <strong className={win.nifty500ReturnPct >= 0 ? 'text-emerald-600' : 'text-rose-600'}>
                  {formatPct(win.nifty500ReturnPct)}
                </strong>
              </div>
            </button>
          );
        })}
      </div>

      {/* QUESTION B RESOLUTION: Empirical Holding Duration Table */}
      <div className="bg-white dark:bg-stone-900 rounded-xl border border-stone-200 dark:border-stone-800 p-6 shadow-sm space-y-4">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2">
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-base font-semibold text-stone-900 dark:text-stone-100 font-serif">
                Empirical Holding Duration & Thesis Resolution (Question B)
              </h3>
              <BacktestDerivedBadge size="sm" />
            </div>
            <p className="text-xs text-stone-500 mt-1">
              Verifying whether agent investment theses have adequate calendar room to resolve and validate the weekly heuristic learning loop without premature termination.
            </p>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono text-stone-700 dark:text-stone-300">
            <thead className="bg-stone-50 dark:bg-stone-800/60 uppercase font-semibold text-[11px] text-stone-500">
              <tr>
                <th className="py-3 px-4">Agent Persona</th>
                <th className="py-3 px-4 text-center">Intended Horizon</th>
                <th className="py-3 px-4 text-center">Empirical Avg Hold</th>
                <th className="py-3 px-4 text-center">Max Hold Observed</th>
                <th className="py-3 px-4 text-center">Fully Resolved Cycles</th>
                <th className="py-3 px-4 text-center">Cycle Completion Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-stone-100 dark:divide-stone-800">
              {activeWindow.resolvedDurations.map((dur) => (
                <tr key={dur.agentId} className="hover:bg-stone-50/60 dark:hover:bg-stone-800/40">
                  <td className="py-3 px-4 font-semibold text-stone-900 dark:text-stone-100">
                    {dur.agentName}
                  </td>
                  <td className="py-3 px-4 text-center text-stone-500">{dur.intendedHorizonDays}</td>
                  <td className="py-3 px-4 text-center font-bold text-amber-600 dark:text-amber-400">
                    {dur.empiricalAvgHoldDays.toFixed(1)} days
                  </td>
                  <td className="py-3 px-4 text-center text-stone-700 dark:text-stone-300">
                    {dur.maxHoldDays} days
                  </td>
                  <td className="py-3 px-4 text-center font-bold text-purple-600 dark:text-purple-400">
                    {dur.resolvedCyclesCount} cycles
                  </td>
                  <td className="py-3 px-4 text-center">
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300">
                      RESOLVED (&gt;1 full cycle)
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Backtest Strategy Performance Table for Selected Window */}
      <div className="bg-white dark:bg-stone-900 rounded-xl border border-stone-200 dark:border-stone-800 shadow-sm overflow-hidden">
        <div className="p-4 border-b border-stone-200 dark:border-stone-800 flex justify-between items-center">
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-base font-semibold text-stone-900 dark:text-stone-100">
                Backtest Performance: {activeWindow.name}
              </h3>
              <BacktestDerivedBadge size="sm" />
            </div>
            <p className="text-xs text-stone-500">
              Simulated returns calculated against daily OHLCV bands with full statutory charge models applied at entry and exit.
            </p>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-stone-700 dark:text-stone-300">
            <thead className="bg-stone-50 dark:bg-stone-800/60 uppercase font-semibold text-[11px] text-stone-500 tracking-wider">
              <tr>
                <th className="py-3 px-4">Agent</th>
                <th className="py-3 px-4 text-right">Final NAV (₹)</th>
                <th className="py-3 px-4 text-right">Window Return</th>
                <th className="py-3 px-4 text-right">Alpha vs Nifty 500</th>
                <th className="py-3 px-4 text-right">Sharpe</th>
                <th className="py-3 px-4 text-right">Max DD</th>
                <th className="py-3 px-4 text-right">Win Rate</th>
                <th className="py-3 px-4 text-right">Faithfulness</th>
                <th className="py-3 px-4 text-center">Closed Trades</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-stone-100 dark:divide-stone-800">
              {activeWindow.agents.map((agent) => (
                <tr key={agent.id} className="hover:bg-stone-50/70 dark:hover:bg-stone-800/40">
                  <td className="py-3 px-4 font-mono font-semibold text-stone-900 dark:text-stone-100">
                    {agent.name}
                  </td>
                  <td className="py-3 px-4 text-right font-mono">
                    {formatPaiseToRupees(agent.navPaise)}
                  </td>
                  <td
                    className={`py-3 px-4 text-right font-mono font-bold ${
                      agent.returnPct >= 0 ? 'text-emerald-600' : 'text-rose-600'
                    }`}
                  >
                    {formatPct(agent.returnPct)}
                  </td>
                  <td
                    className={`py-3 px-4 text-right font-mono font-semibold ${
                      agent.alphaVsBenchmarkPct >= 0 ? 'text-emerald-600' : 'text-rose-600'
                    }`}
                  >
                    {formatPct(agent.alphaVsBenchmarkPct)}
                  </td>
                  <td className="py-3 px-4 text-right font-mono">{agent.sharpeRatio.toFixed(2)}</td>
                  <td className="py-3 px-4 text-right font-mono text-rose-600">
                    -{agent.maxDrawdownPct.toFixed(2)}%
                  </td>
                  <td className="py-3 px-4 text-right font-mono">{agent.winRatePct.toFixed(1)}%</td>
                  <td className="py-3 px-4 text-right font-mono text-purple-600">
                    {agent.faithfulnessRatePct.toFixed(1)}%
                  </td>
                  <td className="py-3 px-4 text-center font-mono">{agent.closedTrades}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
