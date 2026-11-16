import { useState, useEffect } from 'react';
import type { NavHistoryPoint } from '../types';
import { apiService } from '../services/api';
import { CategoryBadge } from '../components/ui/CategoryBadge';
import EquityCurve from '../components/EquityCurve';
import { cn } from '../utils/cn';

interface RegimeWindow {
  id: string;
  name: string;
  shortLabel: string;
  runId: string;
  period: string;
  sessions: number;
  vix: number;
  regime: 'BULL' | 'SIDEWAYS' | 'CORRECTION';
  regimeBadgeText: string;
  nifty500ReturnPct: number;
}

const VETTED_WINDOWS: RegimeWindow[] = [
  {
    id: 'rolling_w1_vetted',
    name: 'Sustained Bull Expansion',
    shortLabel: 'Bull Expansion',
    runId: 'rolling_w1_vetted',
    period: '28 Feb 2025 – 21 Nov 2025',
    sessions: 180,
    vix: 13.8,
    regime: 'BULL',
    regimeBadgeText: 'BULL',
    nifty500ReturnPct: 19.89,
  },
  {
    id: 's1_vetted',
    name: 'Range Compression Chop',
    shortLabel: 'Sideways Chop',
    runId: 's1_vetted',
    period: '24 Nov 2025 – 04 Feb 2026',
    sessions: 51,
    vix: 11.3,
    regime: 'SIDEWAYS',
    regimeBadgeText: 'SIDEWAYS',
    nifty500ReturnPct: -0.60,
  },
  {
    id: 'w2_vetted',
    name: 'High-Vol Correction & Recovery',
    shortLabel: 'High-Vol Correction',
    runId: 'w2_vetted',
    period: '05 Feb 2026 – 29 Oct 2026',
    sessions: 180,
    vix: 22.4,
    regime: 'CORRECTION',
    regimeBadgeText: 'CORRECTION',
    nifty500ReturnPct: 0.36,
  },
];

interface PhilosophyDurationGroup {
  philosophy: string;
  strategies: {
    agent: string;
    type: 'LLM' | 'RULES';
    target: string;
    empirical: string;
    maxHold: string;
    resolution: string;
  }[];
}

const PHILOSOPHY_GROUPS: PhilosophyDurationGroup[] = [
  {
    philosophy: 'Quantitative Momentum',
    strategies: [
      { agent: 'Jim Simons', type: 'LLM', target: '1–10 Days', empirical: '6.4 Days', maxHold: '18 Days', resolution: 'Trailing Stop / Time Decay' },
      { agent: 'Simons Rules Baseline', type: 'RULES', target: '1–10 Days', empirical: '4.8 Days', maxHold: '10 Days', resolution: 'Fixed 2.5x ATR Trailing Stop' },
    ],
  },
  {
    philosophy: 'Dual-Confluence Swing',
    strategies: [
      { agent: 'StockMinds Core', type: 'LLM', target: '5–20 Days', empirical: '14.2 Days', maxHold: '31 Days', resolution: 'Target Reached / Confluence Break' },
      { agent: 'Varsity Rules Baseline', type: 'RULES', target: '5–20 Days', empirical: '12.0 Days', maxHold: '20 Days', resolution: 'Rigid EMA 20/50 Stop' },
    ],
  },
  {
    philosophy: 'GARP Compounding',
    strategies: [
      { agent: 'Peter Lynch', type: 'LLM', target: '15–60 Days', empirical: '38.6 Days', maxHold: '72 Days', resolution: 'Valuation Cap / Deterioration' },
      { agent: 'Lynch Rules Baseline', type: 'RULES', target: '15–60 Days', empirical: '42.1 Days', maxHold: '60 Days', resolution: 'Mechanical PEG > 1.2 Exit' },
    ],
  },
  {
    philosophy: 'Contrarian Value',
    strategies: [
      { agent: 'Howard Marks', type: 'LLM', target: '30–90 Days', empirical: '52.1 Days', maxHold: '112 Days', resolution: 'Mean Reversion / Target Met' },
      { agent: 'Marks Rules Baseline', type: 'RULES', target: '30–90 Days', empirical: '48.5 Days', maxHold: '90 Days', resolution: 'Fixed Valuation Target / Time Stop' },
    ],
  },
  {
    philosophy: 'Secular Domestic Growth',
    strategies: [
      { agent: 'Rakesh Jhunjhunwala', type: 'LLM', target: '90–180 Days', empirical: '84.3 Days', maxHold: '164 Days', resolution: 'Thesis Fulfillment / Rebalance' },
      { agent: 'Jhunjhunwala Rules Baseline', type: 'RULES', target: '90–180 Days', empirical: '91.0 Days', maxHold: '180 Days', resolution: 'Quarterly Fixed Rebalance' },
    ],
  },
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
      
      {/* 1. STANDARDIZED HEADER & STREAMLINED REGIME SWITCHER (MATCHING COMPARISON) */}
      <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-4 border-b border-border-hairline pb-4">
        
        {/* Left: Active Regime Identity & Key Context */}
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-2.5">
            <h1 className="text-2xl sm:text-3xl font-display font-medium tracking-tight text-white">
              {activeWindow.name}
            </h1>
            <span
              className={cn(
                "text-xs px-2 py-0.5 rounded font-mono font-semibold tracking-wider",
                activeWindow.regime === 'BULL'
                  ? "bg-emerald-500/15 text-positive border border-emerald-500/30"
                  : activeWindow.regime === 'CORRECTION'
                  ? "bg-rose-500/15 text-negative border border-rose-500/30"
                  : "bg-zinc-800 text-zinc-300 border border-zinc-700"
              )}
            >
              {activeWindow.regimeBadgeText}
            </span>
            <span className="text-zinc-600 hidden sm:inline">·</span>
            <span className="text-xs sm:text-sm font-mono text-zinc-400">
              Nifty 500: <strong className={cn("font-bold tabular-nums", activeWindow.nifty500ReturnPct >= 0 ? "text-positive" : "text-negative")}>
                {activeWindow.nifty500ReturnPct >= 0 ? '+' : ''}{activeWindow.nifty500ReturnPct.toFixed(2)}%
              </strong>
            </span>
          </div>

          <p className="text-xs sm:text-sm text-zinc-400 font-mono">
            {activeWindow.period} · {activeWindow.sessions} Sessions · India VIX {activeWindow.vix.toFixed(1)} · ₹5L Seed
          </p>
        </div>

        {/* Right: Compact 3-Regime Segmented Switcher */}
        <div
          role="tablist"
          aria-label="Macro regime windows"
          className="flex items-center p-0.5 rounded-md bg-surface-well border border-border-hairline text-xs sm:text-sm font-mono flex-shrink-0"
        >
          {VETTED_WINDOWS.map((win) => (
            <button
              key={win.id}
              role="tab"
              aria-selected={selectedWindowId === win.id}
              onClick={() => setSelectedWindowId(win.id)}
              className={cn(
                "px-3.5 py-1.5 rounded transition-colors cursor-pointer text-xs sm:text-sm whitespace-nowrap",
                selectedWindowId === win.id
                  ? "bg-brand-blue-soft text-brand-blue-text font-semibold border border-brand-blue/40"
                  : "text-zinc-400 hover:text-white border border-transparent"
              )}
            >
              {win.shortLabel}
            </button>
          ))}
        </div>
      </div>

      {/* 2. MULTI-AGENT EQUITY GROWTH COMBAT CURVES */}
      <section className="space-y-3">
        {loading ? (
          <div className="border border-border-hairline bg-surface-inset rounded-lg p-20 text-center text-zinc-500 font-mono text-sm flex justify-center items-center gap-3">
            <div className="w-5 h-5 border-2 border-brand-blue border-t-transparent rounded-full animate-spin" />
            <span>Synchronizing regime equity growth curves...</span>
          </div>
        ) : (
          <EquityCurve
            data={navHistory}
            title={`${activeWindow.name} — Equity Trajectories`}
            isBacktest={true}
          />
        )}
      </section>

      {/* 3. EMPIRICAL HOLDING DURATION & THESIS RESOLUTION TABLE */}
      <section className="space-y-3 pt-2">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2 border-b border-border-hairline pb-3">
          <div>
            <h2 className="font-display text-base sm:text-lg font-medium text-white">
              Holding Duration & Thesis Resolution
            </h2>
            <p className="text-xs sm:text-sm text-zinc-400 font-mono mt-0.5">
              Observed holding period metrics across 5 autonomous LLM strategies and matched deterministic rules controls
            </p>
          </div>
          <span className="text-xs font-mono text-zinc-400">
            10 Matched Strategies · Out-of-Sample
          </span>
        </div>

        <div className="glow-box rounded-lg">
        <div className="border border-border-hairline bg-surface-inset rounded-lg overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left font-mono text-sm sm:text-base">
              <thead>
                <tr className="bg-surface-well border-b border-border-hairline text-xs sm:text-sm text-zinc-400">
                  <th className="py-3 px-5 font-normal">Strategy / Persona</th>
                  <th className="py-3 px-4 font-normal">Type</th>
                  <th className="py-3 px-4 font-normal text-right">Target Horizon</th>
                  <th className="py-3 px-4 font-normal text-right text-positive">Empirical Mean</th>
                  <th className="py-3 px-4 font-normal text-right text-zinc-300">Max Observed</th>
                  <th className="py-3 px-5 font-normal">Exit Trigger</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-hairline text-zinc-300">
                {PHILOSOPHY_GROUPS.map((group, groupIdx) => (
                  group.strategies.map((strat, stratIdx) => {
                    const isLastInGroup = stratIdx === group.strategies.length - 1;
                    return (
                      <tr
                        key={strat.agent}
                        className={cn(
                          "hover:bg-white/[0.02] transition-colors",
                          groupIdx % 2 === 1 ? "bg-white/[0.01]" : "bg-transparent",
                          isLastInGroup && groupIdx < PHILOSOPHY_GROUPS.length - 1 ? "border-b-2 border-border-hairline" : ""
                        )}
                      >
                        <td className="py-3.5 px-5 font-sans font-medium text-white text-sm sm:text-base whitespace-nowrap">
                          {strat.agent}
                        </td>
                        <td className="py-3.5 px-4 whitespace-nowrap">
                          <CategoryBadge type={strat.type} />
                        </td>
                        <td className="py-3.5 px-4 text-right text-zinc-300 font-medium tabular-nums whitespace-nowrap">
                          {strat.target}
                        </td>
                        <td className="py-3.5 px-4 text-right text-positive font-bold tabular-nums whitespace-nowrap">
                          {strat.empirical}
                        </td>
                        <td className="py-3.5 px-4 text-right text-zinc-100 font-medium tabular-nums whitespace-nowrap">
                          {strat.maxHold}
                        </td>
                        <td className="py-3.5 px-5 text-zinc-200 font-sans text-xs sm:text-sm">
                          {strat.resolution}
                        </td>
                      </tr>
                    );
                  })
                ))}
              </tbody>
            </table>
          </div>
        </div>
        </div>
      </section>

    </div>
  );
}
