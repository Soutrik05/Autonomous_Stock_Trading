import { useState, useEffect, useMemo, useCallback } from 'react';
import type { AgentLeaderboardEntry, NavHistoryPoint, MarketContext } from '../types';
import { apiService } from '../services/api';
import BenchmarkMatrixTable from '../components/BenchmarkMatrixTable';
import { TrajectoryChart, type TrajectoryChartPoint } from '../components/TrajectoryChart';
import { SectionHeader } from '../components/ui/SectionHeader';
import { formatPaiseCompact } from '../utils/formatters';
import { cn } from '../utils/cn';

export default function Leaderboard() {
  const [agents, setAgents] = useState<AgentLeaderboardEntry[]>([]);
  const [navHistory, setNavHistory] = useState<NavHistoryPoint[]>([]);
  const [marketContext, setMarketContext] = useState<MarketContext | null>(null);
  const [strategyFilter, setStrategyFilter] = useState<'ALL' | 'LLM' | 'RULES'>('ALL');
  const [chartMode, setChartMode] = useState<'COMPOSITE' | 'PERSONAS'>('COMPOSITE');
  const [loading, setLoading] = useState(true);

  async function loadData() {
    try {
      const [leaderboardData, navData, macroData] = await Promise.all([
        apiService.getLeaderboard(),
        apiService.getAgentNavHistory(),
        apiService.getMarketContext(),
      ]);
      setAgents(leaderboardData);
      setNavHistory(navData);
      setMarketContext(macroData);
    } catch (err) {
      console.warn('Failed to load leaderboard telemetry:', err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();

    const handleModeChange = () => {
      loadData();
    };
    window.addEventListener('mock_mode_changed', handleModeChange);
    return () => window.removeEventListener('mock_mode_changed', handleModeChange);
  }, []);

  const filtered = useMemo(() => {
    return agents.filter((a) => {
      const isControl =
        a.id.startsWith('baseline-') ||
        a.id.includes('rules') ||
        a.name.toLowerCase().includes('rules');
      if (strategyFilter === 'LLM') return !isControl;
      if (strategyFilter === 'RULES') return isControl;
      return true;
    });
  }, [agents, strategyFilter]);

  const seedCapitalDisplay = useMemo(() => {
    const seed = agents[0]?.startingCapitalPaise;
    return seed ? formatPaiseCompact(seed) : '₹5.00 L';
  }, [agents]);

  // Compute percentage return trajectories from ₹5,00,000 seed (memoized)
  const SEED_NAV = 500000;
  const chartData: TrajectoryChartPoint[] = useMemo(() => {
    return navHistory.map((pt) => {
      const llmAvgNav = (pt.simons + pt.lynch + pt.marks + pt.jhunjhunwala + pt.stockmindsCore) / 5;
      const llmCompositeReturn = ((llmAvgNav - SEED_NAV) / SEED_NAV) * 100;

      const bSimons = pt.baselineSimons ?? pt.simons;
      const bLynch = pt.baselineLynch ?? pt.lynch;
      const bMarks = pt.baselineMarks ?? pt.marks;
      const bRj = pt.baselineRj ?? pt.jhunjhunwala;
      const bVarsity = pt.baselineVarsity ?? pt.stockmindsCore;
      const rulesAvgNav = (bSimons + bLynch + bMarks + bRj + bVarsity) / 5;
      const rulesCompositeReturn = ((rulesAvgNav - SEED_NAV) / SEED_NAV) * 100;

      const niftyReturn = ((pt.nifty500 - SEED_NAV) / SEED_NAV) * 100;

      const simonsReturn = ((pt.simons - SEED_NAV) / SEED_NAV) * 100;
      const marksReturn = ((pt.marks - SEED_NAV) / SEED_NAV) * 100;
      const lynchReturn = ((pt.lynch - SEED_NAV) / SEED_NAV) * 100;

      const dateParts = pt.date.split('-');
      const shortDate = dateParts.length === 3 ? `${dateParts[1]}/${dateParts[2]}` : pt.date;

      return {
        date: shortDate,
        fullDate: pt.date,
        llmComposite: Number(llmCompositeReturn.toFixed(2)),
        rulesComposite: Number(rulesCompositeReturn.toFixed(2)),
        nifty500: Number(niftyReturn.toFixed(2)),
        simons: Number(simonsReturn.toFixed(2)),
        marks: Number(marksReturn.toFixed(2)),
        lynch: Number(lynchReturn.toFixed(2)),
      };
    });
  }, [navHistory]);

  const handleChartModeChange = useCallback((mode: 'COMPOSITE' | 'PERSONAS') => {
    setChartMode(mode);
  }, []);

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-28 flex justify-center items-center">
        <div className="flex items-center gap-3 text-zinc-500 font-mono text-xs">
          <div className="w-4 h-4 border-2 border-accent border-t-transparent rounded-full animate-spin" />
          <span>Synchronizing live agent telemetry...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-8 animate-hero-entrance font-sans">
      {/* 1. LIVE MARKET REGIME & ENVIRONMENT MATRIX (100% Backend-Served) */}
      <div>
        <div className="border border-border-hairline bg-[#161616] rounded-lg p-1 sm:p-2 grid grid-cols-2 md:grid-cols-4 divide-y sm:divide-y-0 sm:divide-x divide-border-hairline font-mono text-xs">
          <div className="p-3 sm:px-4">
            <span className="text-[10px] uppercase tracking-wider text-zinc-500 block">Market Regime</span>
            <div className="text-sm font-semibold text-white mt-1 font-sans">
              {marketContext?.regime && marketContext.regime !== 'UNKNOWN'
                ? marketContext.regime.replace(/_/g, ' ')
                : '—'}
            </div>
            <span className="text-[10px] text-zinc-400 mt-0.5 block">
              {marketContext?.regime && marketContext.regime !== 'UNKNOWN' ? 'Active Framework' : '—'}
            </span>
          </div>

          <div className="p-3 sm:px-4">
            <span className="text-[10px] uppercase tracking-wider text-zinc-500 block">India VIX</span>
            <div className="text-sm font-semibold text-white mt-1 tabular-nums">
              {marketContext?.indiaVix ? marketContext.indiaVix.toFixed(2) : '—'}
            </div>
            <span className="text-[10px] text-zinc-400 mt-0.5 block">
              {marketContext?.indiaVix
                ? marketContext.indiaVix < 18
                  ? 'Normal Band (< 18.0)'
                  : 'Elevated Band (≥ 18.0)'
                : '—'}
            </span>
          </div>

          <div className="p-3 sm:px-4">
            <span className="text-[10px] uppercase tracking-wider text-zinc-500 block">Nifty 500 Trend</span>
            <div className="text-sm font-semibold text-positive mt-1 tabular-nums">
              {marketContext?.nifty500Trend && marketContext.nifty500Trend !== 'UNKNOWN'
                ? marketContext.nifty500Trend
                : '—'}
            </div>
            <span className="text-[10px] text-zinc-400 mt-0.5 block">
              Advance/Decline: {marketContext?.advanceDecline != null ? `${marketContext.advanceDecline.toFixed(2)} A/D` : '—'}
            </span>
          </div>

          <div className="p-3 sm:px-4">
            <span className="text-[10px] uppercase tracking-wider text-zinc-500 block">Fleet Exposure</span>
            <div className="text-sm font-semibold text-accent mt-1 tabular-nums">
              {seedCapitalDisplay} <span className="text-xs text-zinc-400 font-normal">/ Agent</span>
            </div>
            <span className="text-[10px] text-zinc-400 mt-0.5 block">
              10 Matched Trading Agents
            </span>
          </div>
        </div>
      </div>

      {/* 3. MASTER STANDINGS TABLE (Single Source of Truth) */}
      <section className="space-y-3">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
          <SectionHeader
            title="Rankings & Performance Matrix"
            subtitle="Ranked by live mark-to-market return."
          />

          {/* Strategy Filter Tabs */}
          <div className="flex items-center gap-1 p-0.5 rounded-md bg-[#121212] border border-border-hairline text-xs font-mono self-start sm:self-auto flex-shrink-0">
            {(['ALL', 'LLM', 'RULES'] as const).map((filter) => (
              <button
                key={filter}
                onClick={() => setStrategyFilter(filter)}
                className={cn(
                  'px-3 py-1.5 rounded transition-colors cursor-pointer text-xs',
                  strategyFilter === filter
                    ? 'bg-white/[0.1] text-accent font-medium border border-accent/30'
                    : 'text-zinc-400 hover:text-white border border-transparent'
                )}
              >
                {filter === 'ALL'
                  ? 'All Agents (10)'
                  : filter === 'LLM'
                  ? 'LLMs Only (5)'
                  : 'Rules Controls (5)'}
              </button>
            ))}
          </div>
        </div>

        <BenchmarkMatrixTable agents={filtered} navHistory={navHistory} isCompact={false} />
      </section>

      {/* 4. TRAJECTORY VISUALIZATION */}
      <section className="space-y-3">
        <SectionHeader
          title="Observed Return Curves"
          subtitle="Walk-forward daily equity trajectories from inception seed (₹5,00,000 per agent) against the NSE Nifty 500 index."
        />

        <div className="border border-border-hairline bg-[#161616] rounded-lg overflow-hidden">
          <TrajectoryChart
            data={chartData}
            mode={chartMode}
            onModeChange={handleChartModeChange}
          />
        </div>
      </section>
    </div>
  );
}
