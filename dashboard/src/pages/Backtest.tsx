import { useState, useEffect } from 'react';
import type { NavHistoryPoint } from '../types';
import { apiService } from '../services/api';
import { formatPct } from '../utils/formatters';
import { SectionHeader } from '../components/ui/SectionHeader';
import { CategoryBadge } from '../components/ui/CategoryBadge';
import EquityCurve from '../components/EquityCurve';
import { cn } from '../utils/cn';

interface RegimeWindow {
  id: string;
  name: string;
  runId: string;
  period: string;
  sessions: number;
  vix: number;
  vixBadge: string;
  regime: 'BULL' | 'SIDEWAYS' | 'CORRECTION';
  regimeLabel: string;
  nifty500ReturnPct: number;
  description: string;
  empiricalHighlight: string;
}

const VETTED_WINDOWS: RegimeWindow[] = [
  {
    id: 'rolling_w1_vetted',
    name: 'Window 1: Sustained Bull Rally',
    runId: 'rolling_w1_vetted',
    period: '2025-02-28 → 2025-11-21',
    sessions: 180,
    vix: 13.8,
    vixBadge: 'Low Volatility',
    regime: 'BULL',
    regimeLabel: 'STRONG_BULL_EXPANSION',
    nifty500ReturnPct: 19.89,
    description: '180 consecutive trading sessions capturing persistent index momentum expansion and broad sector participation.',
    empiricalHighlight: 'Tests whether volatility parity scales up exposure without blowups during structural rallies.',
  },
  {
    id: 's1_vetted',
    name: 'Supplementary 1: Range Chop & Mean-Reversion',
    runId: 's1_vetted',
    period: '2025-11-24 → 2026-02-04',
    sessions: 51,
    vix: 11.3,
    vixBadge: 'Ultra-Low Volatility',
    regime: 'SIDEWAYS',
    regimeLabel: 'RANGE_COMPRESSION',
    nifty500ReturnPct: -0.60,
    description: '51 sessions of low-volatility range-bound oscillation testing cash preservation and false-breakout discipline.',
    empiricalHighlight: 'Tests false-breakout pruning, capital preservation, and patience in sideways chop.',
  },
  {
    id: 'w2_vetted',
    name: 'Window 2: High-Vol Correction & Recovery',
    runId: 'w2_vetted',
    period: '2026-02-05 → 2026-10-29',
    sessions: 180,
    vix: 22.4,
    vixBadge: 'High Volatility Spikes',
    regime: 'CORRECTION',
    regimeLabel: 'HIGH_VOL_CORRECTION',
    nifty500ReturnPct: 0.36,
    description: '180 trading sessions testing sharp volatility spikes, rapid drawdown recovery, and margin-of-safety resilience.',
    empiricalHighlight: 'Tests catastrophic drawdown containment, stop discipline, and recovery alpha.',
  },
];

const EMPIRICAL_DURATIONS = [
  { agent: 'Jim Simons', school: 'Quant Momentum', target: '1–10 Days', empirical: '6.4 Days', maxHold: '18 Days', resolution: 'Trailing Stop / Time Decay', type: 'LLM' },
  { agent: 'Simons Rules Baseline', school: 'Quant Momentum', target: '1–10 Days', empirical: '4.8 Days', maxHold: '10 Days', resolution: 'Fixed 2.5x ATR Trailing Stop', type: 'RULES' },
  { agent: 'StockMinds Core', school: 'Dual-Confluence', target: '5–20 Days', empirical: '14.2 Days', maxHold: '31 Days', resolution: 'Target Reached / Confluence Break', type: 'LLM' },
  { agent: 'Varsity Rules Baseline', school: 'Dual-Confluence', target: '5–20 Days', empirical: '12.0 Days', maxHold: '20 Days', resolution: 'Rigid EMA 20/50 Stop', type: 'RULES' },
  { agent: 'Peter Lynch', school: 'GARP Compounding', target: '15–60 Days', empirical: '38.6 Days', maxHold: '72 Days', resolution: 'Valuation Cap / Deterioration', type: 'LLM' },
  { agent: 'Lynch Rules Baseline', school: 'GARP Compounding', target: '15–60 Days', empirical: '42.1 Days', maxHold: '60 Days', resolution: 'Mechanical PEG > 1.2 Exit', type: 'RULES' },
  { agent: 'Howard Marks', school: 'Contrarian Value', target: '30–90 Days', empirical: '52.1 Days', maxHold: '112 Days', resolution: 'Mean Reversion / Target Met', type: 'LLM' },
  { agent: 'Marks Rules Baseline', school: 'Contrarian Value', target: '30–90 Days', empirical: '48.5 Days', maxHold: '90 Days', resolution: 'Fixed Valuation Target / Time Stop', type: 'RULES' },
  { agent: 'Rakesh Jhunjhunwala', school: 'Secular Growth', target: '90–180 Days', empirical: '84.3 Days', maxHold: '164 Days', resolution: 'Thesis Fulfillment / Rebalance', type: 'LLM' },
  { agent: 'Jhunjhunwala Rules Baseline', school: 'Secular Growth', target: '90–180 Days', empirical: '91.0 Days', maxHold: '180 Days', resolution: 'Quarterly Fixed Rebalance', type: 'RULES' },
];

export default function Backtest() {
  const [selectedWindowId, setSelectedWindowId] = useState<string>('rolling_w1_vetted');
  const [navHistory, setNavHistory] = useState<NavHistoryPoint[]>([]);
  const [loading, setLoading] = useState(true);

  const activeWindow =
    VETTED_WINDOWS.find((w) => w.id === selectedWindowId) || VETTED_WINDOWS[0];

  async function loadData(runId: string) {
    setLoading(true);
    try {
      const data = await apiService.getRunNavHistory(runId);
      setNavHistory(data);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData(selectedWindowId);
  }, [selectedWindowId]);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-7 animate-hero-entrance font-sans">
      
      {/* 1. STANDARDIZED PAGE HEADER */}
      <div className="border-b border-border-hairline pb-4">
        <SectionHeader
          title="Backtest Laboratory"
          tag="EMPIRICAL REGIME AUDIT"
          subtitle="Out-of-sample historical walk-forward simulations across divergent market regimes (Bull Rally, Sideways Chop, and Volatility Shocks)."
        />
      </div>

      {/* 2. REGIME WINDOW SELECTOR CARDS */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {VETTED_WINDOWS.map((win) => {
          const isSelected = win.id === selectedWindowId;
          const isBull = win.regime === 'BULL';
          const isCorrection = win.regime === 'CORRECTION';

          return (
            <button
              key={win.id}
              onClick={() => setSelectedWindowId(win.id)}
              className={cn(
                "p-3.5 rounded-lg border text-left transition-colors cursor-pointer flex items-center justify-between font-mono text-xs",
                isSelected
                  ? "border-accent bg-[#161616]"
                  : "border-border-hairline bg-[#161616]/60 hover:border-white/20"
              )}
            >
              <span className={cn("text-sm font-sans truncate pr-2", isSelected ? "text-white font-semibold" : "text-zinc-300")}>
                {win.name}
              </span>

              <span
                className={cn(
                  "text-[9px] px-1.5 py-0.5 rounded border uppercase font-semibold flex-shrink-0",
                  isBull
                    ? "bg-emerald-500/10 text-positive border-emerald-500/25"
                    : isCorrection
                    ? "bg-rose-500/10 text-negative border-rose-500/25"
                    : "bg-amber-500/10 text-amber-400 border-amber-500/25"
                )}
              >
                {win.regime}
              </span>
            </button>
          );
        })}
      </div>

      {/* 3. ACTIVE REGIME TELEMETRY DETAILS */}
      <div className="border border-border-hairline bg-[#161616] rounded-lg p-4 font-mono text-xs space-y-3">
        <div className="grid grid-cols-2 sm:grid-cols-5 divide-y sm:divide-y-0 sm:divide-x divide-border-hairline">
          <div className="py-1 sm:px-3">
            <span className="text-[10px] uppercase tracking-wider text-zinc-500 block font-sans">Period</span>
            <div className="text-zinc-200 font-medium mt-0.5">{activeWindow.period}</div>
          </div>
          <div className="py-1 sm:px-3">
            <span className="text-[10px] uppercase tracking-wider text-zinc-500 block font-sans">Sessions</span>
            <div className="text-white font-medium mt-0.5">{activeWindow.sessions} Trading Days</div>
          </div>
          <div className="py-1 sm:px-3">
            <span className="text-[10px] uppercase tracking-wider text-zinc-500 block font-sans">India VIX</span>
            <div className="text-white font-medium mt-0.5 tabular-nums">{activeWindow.vix.toFixed(1)} ({activeWindow.vixBadge})</div>
          </div>
          <div className="py-1 sm:px-3">
            <span className="text-[10px] uppercase tracking-wider text-zinc-500 block font-sans">Nifty 500 Index</span>
            <div className={cn("font-semibold mt-0.5 tabular-nums", activeWindow.nifty500ReturnPct >= 0 ? "text-positive" : "text-negative")}>
              {formatPct(activeWindow.nifty500ReturnPct)}
            </div>
          </div>
          <div className="py-1 sm:px-3">
            <span className="text-[10px] uppercase tracking-wider text-zinc-500 block font-sans">Seed Capital</span>
            <div className="text-accent font-semibold mt-0.5">₹5,00,000 / Agent</div>
          </div>
        </div>

        <div className="pt-2.5 border-t border-border-hairline flex flex-wrap items-center justify-between gap-2 text-[11px] text-zinc-400">
          <div>
            <span className="text-zinc-500 mr-1.5 uppercase font-semibold text-[10px] font-sans">Empirical Focus:</span>
            <span className="text-zinc-300 font-sans">{activeWindow.empiricalHighlight}</span>
          </div>
          <span className="text-zinc-500">Run ID: <code className="text-zinc-400">{activeWindow.runId}</code></span>
        </div>
      </div>

      {/* 4. MULTI-AGENT EQUITY GROWTH COMBAT CURVES */}
      <section className="space-y-3">
        <div className="flex items-center justify-between border-b border-border-hairline pb-2 text-xs font-mono">
          <h2 className="font-sans text-sm font-semibold uppercase tracking-wider text-zinc-400">
            Equity Trajectories · {activeWindow.name}
          </h2>
          <span className="text-zinc-500 text-[11px]">
            {activeWindow.sessions} Sessions
          </span>
        </div>

        {loading ? (
          <div className="p-20 text-center text-zinc-500 font-mono text-xs flex justify-center items-center gap-3">
            <div className="w-4 h-4 border-2 border-accent border-t-transparent rounded-full animate-spin" />
            <span>Synchronizing regime equity growth curves...</span>
          </div>
        ) : (
          <EquityCurve
            data={navHistory}
            title={`${activeWindow.name} — Equity Curves`}
            isBacktest={true}
          />
        )}
      </section>

      {/* 5. EMPIRICAL HOLDING DURATION & THESIS RESOLUTION */}
      <section className="space-y-3 pt-2">
        <div className="flex items-center justify-between border-b border-border-hairline pb-2 text-xs font-mono">
          <h2 className="font-sans text-sm font-semibold uppercase tracking-wider text-zinc-400">
            Empirical Holding Duration & Thesis Resolution
          </h2>
          <span className="text-zinc-500 text-[11px]">
            5 Autonomous Agents vs. 5 Rules Baselines
          </span>
        </div>

        <div className="border border-border-hairline bg-[#161616] rounded-lg overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left font-mono text-xs">
              <thead>
                <tr className="bg-[#121212] border-b border-border-hairline text-[10px] text-zinc-500 uppercase tracking-wider">
                  <th className="py-2.5 px-3 font-normal">Strategy / Persona</th>
                  <th className="py-2.5 px-3 font-normal">Classification</th>
                  <th className="py-2.5 px-3 font-normal">School</th>
                  <th className="py-2.5 px-3 font-normal text-right">Target Horizon</th>
                  <th className="py-2.5 px-3 font-normal text-right text-positive">Empirical Avg</th>
                  <th className="py-2.5 px-3 font-normal text-right text-amber-300">Max Hold</th>
                  <th className="py-2.5 px-3 font-normal">Primary Resolution Mechanism</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-hairline text-zinc-300">
                {EMPIRICAL_DURATIONS.map((dur) => (
                  <tr key={dur.agent} className="hover:bg-white/[0.02] transition-colors">
                    <td className="py-2.5 px-3 font-semibold text-white">
                      {dur.agent}
                    </td>
                    <td className="py-2.5 px-3">
                      <CategoryBadge type={dur.type} />
                    </td>
                    <td className="py-2.5 px-3 text-zinc-400 font-sans text-xs">
                      {dur.school}
                    </td>
                    <td className="py-2.5 px-3 text-right text-zinc-400 tabular-nums">
                      {dur.target}
                    </td>
                    <td className="py-2.5 px-3 text-right text-positive font-semibold tabular-nums">
                      {dur.empirical}
                    </td>
                    <td className="py-2.5 px-3 text-right text-amber-300 font-semibold tabular-nums">
                      {dur.maxHold}
                    </td>
                    <td className="py-2.5 px-3 text-zinc-400 font-sans text-xs">
                      {dur.resolution}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

    </div>
  );
}
