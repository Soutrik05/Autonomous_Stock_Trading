import { useState, useEffect, useMemo, useCallback } from 'react';
import type { AgentLeaderboardEntry, NavHistoryPoint, MarketContext } from '../types';
import { apiService, TELEMETRY_POLL_INTERVAL_MS } from '../services/api';
import BenchmarkMatrixTable from '../components/BenchmarkMatrixTable';
import { TrajectoryChart, type TrajectoryChartPoint } from '../components/TrajectoryChart';
import { SectionHeader } from '../components/ui/SectionHeader';
import { cn } from '../utils/cn';

export default function Leaderboard() {
  const [agents, setAgents] = useState<AgentLeaderboardEntry[]>([]);
  const [navHistory, setNavHistory] = useState<NavHistoryPoint[]>([]);
  const [marketContext, setMarketContext] = useState<MarketContext | null>(null);
  const [strategyFilter, setStrategyFilter] = useState<'ALL' | 'LLM' | 'RULES'>('ALL');
  const [chartMode, setChartMode] = useState<'COMPOSITE' | 'PERSONAS'>('COMPOSITE');
  const [loading, setLoading] = useState(true);

  async function loadData(isBackground = false) {
    if (!isBackground) setLoading(true);
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
      if (!isBackground) setLoading(false);
    }
  }

  useEffect(() => {
    loadData(false);

    // Dynamic background polling on synchronized cadence (10 min)
    const pollInterval = setInterval(() => {
      loadData(true);
    }, TELEMETRY_POLL_INTERVAL_MS);

    const handleModeChange = () => {
      loadData(false);
    };
    window.addEventListener('mock_mode_changed', handleModeChange);
    return () => {
      clearInterval(pollInterval);
      window.removeEventListener('mock_mode_changed', handleModeChange);
    };
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

  const SEED_NAV = 500000;

  // 1. Dynamic India VIX from macro.db via backend API
  const vixHeadline = useMemo(() => {
    return marketContext?.indiaVix != null ? marketContext.indiaVix.toFixed(2) : '—';
  }, [marketContext?.indiaVix]);

  // 2. Dynamic Nifty 500 20-Day Trend & A/D Breadth directly from backend API
  const { niftyTrendLabel, trendColorClass, adRatioText } = useMemo(() => {
    const rawTrend = marketContext?.nifty500Trend;
    let label = 'Sideways';
    let color = 'text-zinc-300';

    if (rawTrend && rawTrend !== 'UNKNOWN') {
      const upper = rawTrend.toUpperCase();
      if (upper === 'BULLISH') {
        label = 'Bullish';
        color = 'text-positive';
      } else if (upper === 'BEARISH') {
        label = 'Bearish';
        color = 'text-negative';
      } else if (upper === 'SIDEWAYS' || upper === 'RANGE_BOUND') {
        label = 'Sideways';
        color = 'text-zinc-300';
      } else {
        label = rawTrend.charAt(0).toUpperCase() + rawTrend.slice(1).toLowerCase();
        color = 'text-zinc-300';
      }
    }

    const adRatio = marketContext?.advanceDecline != null
      ? marketContext.advanceDecline.toFixed(2)
      : '2.00';

    return {
      niftyTrendLabel: label,
      trendColorClass: color,
      adRatioText: adRatio,
    };
  }, [marketContext?.nifty500Trend, marketContext?.advanceDecline]);

  // Compute percentage return trajectories from ₹5,00,000 seed (memoized)
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
      {/* 1. LIVE RANKINGS TABLE (Primary Focus) */}
      <section className="space-y-3">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
          <SectionHeader
            title="Live Rankings"
          />

          <div className="flex flex-wrap items-center gap-2.5 self-start sm:self-auto">
            {/* Market Conditions Compact Inline Ribbon */}
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-md bg-[#161616] border border-border-hairline text-[12px] font-mono">
              <span className="text-zinc-500 text-[11px]">Nifty 500 Trend:</span>
              <span className={cn("font-medium", trendColorClass)}>{niftyTrendLabel}</span>
              <span className="text-zinc-600">·</span>
              <span className="text-zinc-500 text-[11px]">A/D Ratio:</span>
              <span className="text-zinc-200 font-medium tabular-nums">{adRatioText}</span>
              <span className="text-zinc-600">·</span>
              <span className="text-zinc-500 text-[11px]">India VIX:</span>
              <span className="text-zinc-200 font-medium tabular-nums">{vixHeadline}</span>
            </div>

            {/* Strategy Filter Tabs */}
            <div className="flex items-center gap-1 p-0.5 rounded-md bg-[#121212] border border-border-hairline text-xs font-mono flex-shrink-0">
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
                    ? 'All (10)'
                    : filter === 'LLM'
                      ? 'LLMs (5)'
                      : 'Rules (5)'}
                </button>
              ))}
            </div>
          </div>
        </div>

        <BenchmarkMatrixTable agents={filtered} navHistory={navHistory} isCompact={false} />
      </section>

      {/* 2. TRAJECTORY VISUALIZATION */}
      <section className="space-y-3">
        <SectionHeader
          title="Observed Return Curves"
          subtitle="Walk-forward daily equity trajectories from inception seed (₹5L per agent) against the NSE Nifty 500 index."
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
