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
        <div className="flex items-center gap-3 text-[#7C8698] font-mono text-sm">
          <div className="w-4 h-4 border-2 border-[#8A7441] border-t-transparent rounded-full animate-spin" />
          <span>Loading historical walk-forward backtest data...</span>
        </div>
      </div>
    );
  }

  const activeWindow = windows.find((w) => w.windowId === selectedWindowId) || windows[0];

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8 animate-fade-in font-sans">
      {/* Header */}
      <div className="border-b border-[#DCD7CC] pb-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-mono text-[#5E4B7A] flex items-center gap-1.5 font-medium">
              <History className="w-4 h-4" />
              <span>Walk-forward historical evaluation</span>
            </span>
            <BacktestDerivedBadge size="sm" />
          </div>
          <h1 className="text-3xl font-serif font-bold text-[#151B26]">
            Historical walk-forward backtesting lab
          </h1>
          <p className="text-sm text-[#475060] mt-1 max-w-3xl leading-relaxed">
            Multi-regime 180-day rolling simulation windows with isolated state storage and persistent inference caching. Validates complete holding cycles for long-horizon personas (Jhunjhunwala 90–180d, Lynch 60–120d).
          </p>
        </div>

        {/* Evidence Isolation Notice */}
        <div className="callout-panel px-3 py-2 text-xs font-mono max-w-xs">
          <strong>Strict isolation guardrail:</strong> Evaluated against daily OHLCV bands and permanently isolated from live pilot records.
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
              className={`p-4 rounded-[3px] border text-left transition-colors cursor-pointer flex-1 min-w-[280px] ${
                isSelected
                  ? 'border-[#5E4B7A] bg-[#F4F0F9]'
                  : 'border-[#DCD7CC] bg-white hover:bg-[#F6F4EF]'
              }`}
            >
              <div className="flex justify-between items-center mb-1">
                <span className="font-mono text-xs text-[#7C8698]">
                  {win.startDate} → {win.endDate}
                </span>
                <span
                  className={`text-[10px] font-mono px-2 py-0.5 rounded-[2px] border font-medium ${
                    isBull ? 'bg-[#EBF5F0] text-[#1E6548] border-[#A3D4BE]' : 'bg-[#F3EFE6] text-[#8A7441] border-[#D6C7A1]'
                  }`}
                >
                  {win.marketRegime} regime
                </span>
              </div>
              <div className="font-serif font-bold text-[#151B26] text-base mt-1">
                {win.name}
              </div>
              <div className="text-xs text-[#475060] mt-2 font-mono flex items-center gap-1">
                <span>Nifty 500 index:</span>
                <strong className={win.nifty500ReturnPct >= 0 ? 'text-[#1E6548]' : 'text-[#933835]'}>
                  {formatPct(win.nifty500ReturnPct)}
                </strong>
              </div>
            </button>
          );
        })}
      </div>

      {/* Empirical Holding Duration Table */}
      <div className="ledger-panel p-6 space-y-4">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-base font-serif font-bold text-[#151B26]">
              Empirical holding duration & thesis resolution
            </h3>
            <BacktestDerivedBadge size="sm" />
          </div>
          <p className="text-xs text-[#7C8698] mt-1">
            Empirical verification that agent holding theses have completed full cycles, validating that the weekly heuristic reflection loop exercises over historical calendar spans.
          </p>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono text-[#151B26]">
            <thead className="bg-[#F6F4EF] text-[11px] text-[#475060] border-b border-[#DCD7CC]">
              <tr>
                <th className="py-2.5 px-4 font-medium">Agent persona</th>
                <th className="py-2.5 px-4 text-center font-medium">Intended horizon</th>
                <th className="py-2.5 px-4 text-center font-medium">Empirical avg hold</th>
                <th className="py-2.5 px-4 text-center font-medium">Max hold observed</th>
                <th className="py-2.5 px-4 text-center font-medium">Resolved full cycles</th>
                <th className="py-2.5 px-4 text-center font-medium">Cycle status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E7E3D9]">
              {activeWindow.resolvedDurations.map((dur) => (
                <tr key={dur.agentId} className="hover:bg-[#F6F4EF] transition-colors">
                  <td className="py-3 px-4 font-medium">{dur.agentName}</td>
                  <td className="py-3 px-4 text-center text-[#475060]">{dur.intendedHorizonDays}</td>
                  <td className="py-3 px-4 text-center font-medium text-[#8A7441]">
                    {dur.empiricalAvgHoldDays.toFixed(1)} days
                  </td>
                  <td className="py-3 px-4 text-center text-[#475060]">{dur.maxHoldDays} days</td>
                  <td className="py-3 px-4 text-center font-medium text-[#5E4B7A]">
                    {dur.resolvedCyclesCount} cycles
                  </td>
                  <td className="py-3 px-4 text-center">
                    <span className="inline-flex items-center px-2 py-0.5 rounded-[2px] text-[10px] font-medium bg-[#EBF5F0] text-[#1E6548] border border-[#A3D4BE]">
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
      <div className="ledger-panel overflow-hidden">
        <div className="p-4 border-b border-[#E7E3D9] flex justify-between items-center bg-white">
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-base font-serif font-bold text-[#151B26]">
                Backtest results: {activeWindow.name}
              </h3>
              <BacktestDerivedBadge size="sm" />
            </div>
            <p className="text-xs text-[#7C8698]">
              Calculated against daily OHLCV bands with full statutory charges applied at entry and exit.
            </p>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono text-[#151B26]">
            <thead className="bg-[#F6F4EF] text-[11px] text-[#475060] border-b border-[#DCD7CC]">
              <tr>
                <th className="py-2.5 px-4 font-medium">Agent</th>
                <th className="py-2.5 px-4 text-right font-medium">Final NAV (₹)</th>
                <th className="py-2.5 px-4 text-right font-medium">Return</th>
                <th className="py-2.5 px-4 text-right font-medium">Alpha vs N500</th>
                <th className="py-2.5 px-4 text-right font-medium">Sharpe</th>
                <th className="py-2.5 px-4 text-right font-medium">Max drawdown</th>
                <th className="py-2.5 px-4 text-right font-medium">Win rate</th>
                <th className="py-2.5 px-4 text-right font-medium">Faithfulness</th>
                <th className="py-2.5 px-4 text-center font-medium">Closed trades</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E7E3D9]">
              {activeWindow.agents.map((ag) => (
                <tr key={ag.id} className="hover:bg-[#F6F4EF] transition-colors">
                  <td className="py-3 px-4 font-semibold">{ag.name}</td>
                  <td className="py-3 px-4 text-right font-medium">{formatPaiseToRupees(ag.navPaise)}</td>
                  <td className={`py-3 px-4 text-right font-semibold ${ag.returnPct >= 0 ? 'text-[#1E6548]' : 'text-[#933835]'}`}>
                    {formatPct(ag.returnPct)}
                  </td>
                  <td className={`py-3 px-4 text-right font-medium ${ag.alphaVsBenchmarkPct >= 0 ? 'text-[#1E6548]' : 'text-[#933835]'}`}>
                    {ag.alphaVsBenchmarkPct >= 0 ? `+${formatPct(ag.alphaVsBenchmarkPct)}` : formatPct(ag.alphaVsBenchmarkPct)}
                  </td>
                  <td className="py-3 px-4 text-right">{ag.sharpeRatio.toFixed(2)}</td>
                  <td className="py-3 px-4 text-right text-[#933835]">-{ag.maxDrawdownPct.toFixed(2)}%</td>
                  <td className="py-3 px-4 text-right">{ag.winRatePct.toFixed(1)}%</td>
                  <td className="py-3 px-4 text-right text-[#5E4B7A]">{ag.faithfulnessRatePct.toFixed(1)}%</td>
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
