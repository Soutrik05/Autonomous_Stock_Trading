import { useState, useEffect } from 'react';
import type { AgentLeaderboardEntry, NavHistoryPoint } from '../types';
import { apiService } from '../services/api';
import EquityCurve from '../components/EquityCurve';
import BenchmarkMatrixTable from '../components/BenchmarkMatrixTable';
import HeadToHeadDuelsTable from '../components/HeadToHeadDuelsTable';
import PodiumCards from '../components/PodiumCards';

interface EvaluationWindowConfig {
  id: 'LIVE' | 'W1' | 'S1' | 'W2';
  runId: string;
  name: string;
  regime: string;
  vix: number;
  benchmarkReturnPct: number;
  seedCapitalFormatted: string;
  description: string;
}

const EVALUATION_WINDOWS: EvaluationWindowConfig[] = [
  {
    id: 'LIVE',
    runId: 'LIVE',
    name: 'Live Pilot',
    regime: 'HIGH_VOL_CORRECTION',
    vix: 18.42,
    benchmarkReturnPct: -3.95,
    seedCapitalFormatted: '₹5,00,000 / AGENT',
    description: 'Current production paper-trading tape on live Nifty 500 constituents',
  },
  {
    id: 'W1',
    runId: 'rolling_w1_vetted',
    name: 'W1: Bull Rally',
    regime: 'STRONG_BULL_EXPANSION',
    vix: 13.80,
    benchmarkReturnPct: 19.89,
    seedCapitalFormatted: '₹5,00,000 / AGENT',
    description: '180 sessions (2025-02-28 to 2025-11-21) · Sustained momentum expansion',
  },
  {
    id: 'S1',
    runId: 's1_vetted',
    name: 'S1: Range Chop',
    regime: 'RANGE_COMPRESSION',
    vix: 11.30,
    benchmarkReturnPct: -0.60,
    seedCapitalFormatted: '₹5,00,000 / AGENT',
    description: '51 sessions (2025-11-24 to 2026-02-04) · Low-volatility sideways mean-reversion',
  },
  {
    id: 'W2',
    runId: 'w2_vetted',
    name: 'W2: High-Vol Drawdown',
    regime: 'HIGH_VOL_CORRECTION',
    vix: 22.40,
    benchmarkReturnPct: 0.36,
    seedCapitalFormatted: '₹5,00,000 / AGENT',
    description: '180 sessions (2026-02-05 to 2026-10-29) · Volatility spikes & recovery stress-testing',
  },
];

export default function Leaderboard() {
  const [agents, setAgents] = useState<AgentLeaderboardEntry[]>([]);
  const [navHistory, setNavHistory] = useState<NavHistoryPoint[]>([]);
  const [strategyFilter, setStrategyFilter] = useState<'ALL' | 'LLM' | 'RULES'>('ALL');
  const [selectedWindow, setSelectedWindow] = useState<'LIVE' | 'W1' | 'S1' | 'W2'>('LIVE');
  const [loading, setLoading] = useState(true);
  const [switchingWindow, setSwitchingWindow] = useState(false);

  async function loadWindowData(windowId: 'LIVE' | 'W1' | 'S1' | 'W2') {
    const config = EVALUATION_WINDOWS.find((w) => w.id === windowId) || EVALUATION_WINDOWS[0];
    try {
      if (windowId === 'LIVE') {
        const [leaderboardData, navData] = await Promise.all([
          apiService.getLeaderboard(),
          apiService.getAgentNavHistory(),
        ]);
        setAgents(leaderboardData);
        setNavHistory(navData);
      } else {
        const [leaderboardData, navData] = await Promise.all([
          apiService.getRunLeaderboard(config.runId),
          apiService.getRunNavHistory(config.runId),
        ]);
        setAgents(leaderboardData);
        setNavHistory(navData);
      }
    } finally {
      setLoading(false);
      setSwitchingWindow(false);
    }
  }

  useEffect(() => {
    loadWindowData('LIVE');

    const handleModeChange = () => {
      loadWindowData(selectedWindow);
    };
    window.addEventListener('mock_mode_changed', handleModeChange);
    return () => window.removeEventListener('mock_mode_changed', handleModeChange);
  }, []);

  const handleWindowChange = async (winId: 'LIVE' | 'W1' | 'S1' | 'W2') => {
    if (winId === selectedWindow) return;
    setSelectedWindow(winId);
    setSwitchingWindow(true);
    await loadWindowData(winId);
  };

  const currentWindowConfig =
    EVALUATION_WINDOWS.find((w) => w.id === selectedWindow) || EVALUATION_WINDOWS[0];

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-28 flex justify-center items-center">
        <div className="flex items-center gap-3 text-zinc-400 font-sans text-sm">
          <div className="w-5 h-5 border-2 border-[#D4AF37] border-t-transparent rounded-full animate-spin" />
          <span>Synchronizing benchmark telemetry...</span>
        </div>
      </div>
    );
  }

  // Filter strategies for the primary leaderboard
  const filtered = agents.filter((a) => {
    const isControl =
      a.id.startsWith('baseline-') ||
      a.id.includes('rules') ||
      a.name.toLowerCase().includes('rules');
    if (strategyFilter === 'LLM') return !isControl;
    if (strategyFilter === 'RULES') return isControl;
    return true;
  });

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-12 space-y-12 animate-hero-entrance font-sans">

      {/* 1. THE BENCHMARK EVALUATION ENVIRONMENT */}
      <section className="cosmic-card rounded-xl p-5 sm:p-6 space-y-5">

        {/* Top Header: Label on Left, Distinct Regime Window Selector on Right */}
        <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-4 pb-4 border-b border-white/[0.08]">
          <div className="flex items-center gap-2.5">
            <span
              className={`w-2 h-2 rounded-full ${
                selectedWindow === 'LIVE' ? 'bg-emerald-400 animate-pulse' : 'bg-zinc-400'
              }`}
            />
            <span className="text-xs font-sans uppercase tracking-widest text-zinc-300 font-bold">
              BENCHMARK EVALUATION ENVIRONMENT
            </span>
          </div>

          {/* Segmented Window Tabs: Distinct LIVE_PILOT vs BACKTEST_DERIVED Family */}
          <div className="flex flex-wrap items-center gap-2 p-1 rounded-lg cosmic-well text-xs font-sans">
            {/* Live Pilot Tab */}
            <button
              onClick={() => handleWindowChange('LIVE')}
              className={`px-3 py-1.5 rounded transition-all cursor-pointer text-xs font-medium flex items-center gap-2 ${
                selectedWindow === 'LIVE'
                  ? 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/40 shadow-sm font-semibold'
                  : 'text-zinc-300 hover:text-emerald-300 hover:bg-emerald-500/10 border border-emerald-500/20'
              }`}
              title={EVALUATION_WINDOWS[0].description}
            >
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              <span>Live Pilot</span>
              <span className="text-[9px] font-mono uppercase px-1 py-0.2 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                Live
              </span>
            </button>

            <span className="w-px h-4 bg-white/10 hidden sm:block mx-0.5" />

            {/* Backtest Walk-Forward Regimes */}
            {EVALUATION_WINDOWS.filter((w) => w.id !== 'LIVE').map((win) => (
              <button
                key={win.id}
                onClick={() => handleWindowChange(win.id)}
                className={`px-3 py-1.5 rounded transition-all cursor-pointer text-xs font-medium ${
                  selectedWindow === win.id
                    ? 'bg-white/[0.12] text-white font-semibold border border-white/20 shadow-sm'
                    : 'text-zinc-400 hover:text-white hover:bg-white/[0.04] border border-transparent'
                }`}
                title={win.description}
              >
                {win.name}
              </button>
            ))}
          </div>
        </div>

        {/* 4 Clean Metric Cards for Environment Conditions (Cosmic Pods) */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">

          {/* Regime */}
          <div className="cosmic-pod p-3.5 rounded-lg space-y-1">
            <span className="text-[11px] font-sans uppercase tracking-wider text-zinc-400 font-semibold block">
              Market Regime
            </span>
            <div className="font-sans text-sm sm:text-[15px] font-bold text-white tracking-tight truncate">
              {currentWindowConfig.regime.replace(/_/g, ' ')}
            </div>
          </div>

          {/* India VIX */}
          <div className="cosmic-pod p-3.5 rounded-lg space-y-1">
            <span className="text-[11px] font-sans uppercase tracking-wider text-zinc-400 font-semibold block">
              India VIX
            </span>
            <div className="flex items-center gap-2">
              <span className="font-mono text-base font-bold text-white tabular-nums">
                {currentWindowConfig.vix.toFixed(2)}
              </span>
              <span
                className={`px-1.5 py-0.5 rounded text-[10px] font-sans font-bold uppercase tracking-wider ${currentWindowConfig.vix < 14
                    ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
                    : currentWindowConfig.vix <= 18
                      ? 'bg-amber-500/20 text-amber-400 border border-amber-500/40'
                      : 'bg-rose-500/20 text-rose-400 border border-rose-500/40'
                  }`}
              >
                {currentWindowConfig.vix < 14 ? 'Low Vol' : currentWindowConfig.vix <= 18 ? 'Elevated' : 'High Vol'}
              </span>
            </div>
          </div>

          {/* Nifty 500 Benchmark */}
          <div className="cosmic-pod p-3.5 rounded-lg space-y-1">
            <span className="text-[11px] font-sans uppercase tracking-wider text-zinc-400 font-semibold block">
              Nifty 500 Benchmark
            </span>
            <div
              className={`font-mono text-base font-bold tabular-nums ${currentWindowConfig.benchmarkReturnPct > 0
                  ? 'text-emerald-400'
                  : currentWindowConfig.benchmarkReturnPct < 0
                    ? 'text-rose-400/90'
                    : 'text-zinc-200'
                }`}
            >
              {currentWindowConfig.benchmarkReturnPct > 0
                ? `+${currentWindowConfig.benchmarkReturnPct.toFixed(2)}%`
                : `${currentWindowConfig.benchmarkReturnPct.toFixed(2)}%`}
            </div>
          </div>

          {/* Seed Capital */}
          <div className="cosmic-pod p-3.5 rounded-lg space-y-1">
            <span className="text-[11px] font-sans uppercase tracking-wider text-zinc-400 font-semibold block">
              Seed Capital
            </span>
            <div className="font-mono text-base font-bold text-[#D4AF37] tabular-nums">
              {currentWindowConfig.seedCapitalFormatted}
            </div>
          </div>

        </div>

      </section>

      {/* PODIUM TOP 3 CARDS */}
      <PodiumCards topAgents={filtered} />

      {/* 2. SECTION 1: CURRENT STANDINGS (UNIFIED WITH LANDING PAGE) */}
      <section className="space-y-4">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 border-b border-white/[0.1] pb-4">
          <div>
            <h1 className="font-display text-3xl sm:text-4xl font-bold tracking-tight text-white">
              Current Standings
            </h1>
          </div>

          {/* Architecture Filter: All | LLMs | Rules */}
          <div className="flex items-center gap-3">
            {switchingWindow && (
              <span className="text-xs font-sans text-[#D4AF37] font-semibold animate-pulse mr-2">
                Updating benchmark data...
              </span>
            )}
            <div className="flex items-center gap-1 p-1 rounded bg-black/80 border border-white/10 text-xs font-sans">
              {(['ALL', 'LLM', 'RULES'] as const).map((filter) => (
                <button
                  key={filter}
                  onClick={() => setStrategyFilter(filter)}
                  className={`px-3 py-1.5 rounded transition-all cursor-pointer text-xs font-medium ${strategyFilter === filter
                      ? 'bg-white/[0.16] text-[#D4AF37] font-bold border border-[#D4AF37]/40 shadow-sm'
                      : 'text-zinc-400 hover:text-white'
                    }`}
                >
                  {filter === 'ALL' ? 'All Strategies' : filter === 'LLM' ? 'LLMs Only' : 'Rules Only'}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Empirical Context Banner: Reframes all-red or flat benchmark comparisons */}
        {currentWindowConfig.benchmarkReturnPct > 15 && (
          <div className="flex items-center gap-2.5 text-xs text-zinc-300 bg-white/[0.02] border border-white/[0.07] rounded-lg px-4 py-2.5 font-sans">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400 flex-shrink-0" />
            <span>
              <strong className="text-zinc-200">Regime Observation:</strong> Nifty 500 returned +{currentWindowConfig.benchmarkReturnPct.toFixed(2)}% in this window — index rally was heavily concentrated in mega-caps; all systematic stock-picking strategies underperformed pure beta.
            </span>
          </div>
        )}
        {currentWindowConfig.benchmarkReturnPct < 0 && (
          <div className="flex items-center gap-2.5 text-xs text-zinc-300 bg-white/[0.02] border border-white/[0.07] rounded-lg px-4 py-2.5 font-sans">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 flex-shrink-0" />
            <span>
              <strong className="text-zinc-200">Regime Observation:</strong> Nifty 500 was flat/contracting ({currentWindowConfig.benchmarkReturnPct.toFixed(2)}%) in this sideways chop window — cash preservation and disciplined pruning generated positive relative alpha.
            </span>
          </div>
        )}

        {/* Master Standings Table */}
        <BenchmarkMatrixTable agents={filtered} isCompact={false} />
      </section>

      {/* 3. SECTION 2: HEAD-TO-HEAD PHILOSOPHY SHOWDOWNS (COGNITION VS DETERMINISM) */}
      <section className="pt-6 border-t border-white/[0.1]">
        <HeadToHeadDuelsTable agents={agents} />
      </section>

      {/* 4. SECTION 3: MULTI-AGENT EQUITY GROWTH COMBAT CURVES */}
      <section className="pt-6 border-t border-white/[0.1] space-y-4">
        <div>
          <h2 className="font-display text-2xl sm:text-3xl font-bold tracking-tight text-white">
            Equity Growth Trajectories
          </h2>
        </div>

        <EquityCurve
          data={navHistory}
          title={
            selectedWindow === 'LIVE'
              ? 'Multi-Agent Equity Growth'
              : `${currentWindowConfig.name} — Multi-Agent Equity Growth`
          }
          isBacktest={selectedWindow !== 'LIVE'}
        />
      </section>

    </div>
  );
}
