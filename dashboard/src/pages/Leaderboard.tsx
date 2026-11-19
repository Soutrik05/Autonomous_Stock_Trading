import { useState, useEffect, useMemo } from 'react';
import type { AgentLeaderboardEntry, NavHistoryPoint, MarketContext } from '../types';
import { apiService, TELEMETRY_POLL_INTERVAL_MS } from '../services/api';
import BenchmarkMatrixTable from '../components/BenchmarkMatrixTable';
import AllAgentsReturnChart from '../components/AllAgentsReturnChart';
import { SectionHeader } from '../components/ui/SectionHeader';
import { getCached, setCached } from '../utils/sessionCache';
import { cn } from '../utils/cn';

interface LeaderboardCache {
  agents: AgentLeaderboardEntry[];
  navHistory: NavHistoryPoint[];
  marketContext: MarketContext | null;
}

// This page's own bundle (agents + nav history + market context) is cached separately from
// the plain agents array, which other pages (Portfolio, Comparison) cache under the shared
// 'leaderboard' key -- two different shapes, so they must not share one key.
const CACHE_KEY = 'leaderboard_page';
const SHARED_AGENTS_CACHE_KEY = 'leaderboard';

export default function Leaderboard() {
  // Seen this session already? Render those real values immediately (no spinner) and just
  // refresh them silently -- a plain page refresh must never show a loading screen for data
  // we already have.
  const [cachedOnMount] = useState(() => getCached<LeaderboardCache>(CACHE_KEY));
  const [agents, setAgents] = useState<AgentLeaderboardEntry[]>(cachedOnMount?.agents ?? []);
  const [navHistory, setNavHistory] = useState<NavHistoryPoint[]>(cachedOnMount?.navHistory ?? []);
  const [marketContext, setMarketContext] = useState<MarketContext | null>(cachedOnMount?.marketContext ?? null);
  const [strategyFilter, setStrategyFilter] = useState<'ALL' | 'LLM' | 'RULES'>('ALL');
  const [showRiskMetrics, setShowRiskMetrics] = useState(false);
  const [loading, setLoading] = useState(!cachedOnMount);

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
      setCached<LeaderboardCache>(CACHE_KEY, { agents: leaderboardData, navHistory: navData, marketContext: macroData });
      setCached(SHARED_AGENTS_CACHE_KEY, leaderboardData);
    } catch (err) {
      console.warn('Failed to load leaderboard telemetry:', err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    // Already have real data from this session (cache) -- load the latest quietly instead of
    // flashing the spinner again.
    loadData(!!cachedOnMount);

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
    // eslint-disable-next-line react-hooks/exhaustive-deps
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

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-28 flex justify-center items-center">
        <div className="flex items-center gap-3 text-zinc-500 font-mono text-xs">
          <div className="w-4 h-4 border-2 border-brand-blue border-t-transparent rounded-full animate-spin" />
          <span>Synchronizing leaderboard data...</span>
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
            variant="page"
          />

          <div className="flex flex-wrap items-center gap-2.5 self-start sm:self-auto">
            {/* Market Conditions Compact Inline Ribbon */}
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-md bg-surface-inset border border-border-hairline text-[12px] font-mono">
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
            <div
              role="tablist"
              aria-label="Strategy cohort filters"
              className="flex items-center gap-1 p-0.5 rounded-md bg-surface-well border border-border-hairline text-xs font-mono flex-shrink-0"
            >
              {(['ALL', 'LLM', 'RULES'] as const).map((filter) => (
                <button
                  key={filter}
                  role="tab"
                  aria-selected={strategyFilter === filter}
                  onClick={() => setStrategyFilter(filter)}
                  className={cn(
                    'px-3 py-1.5 rounded transition-colors cursor-pointer text-xs',
                    strategyFilter === filter
                      ? 'bg-brand-blue-soft text-brand-blue-text font-medium border border-brand-blue'
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

            {/* View Mode Toggle: Core View vs Risk Stats */}
            <div
              role="group"
              aria-label="Table view mode"
              className="flex items-center gap-1 p-0.5 rounded-md bg-surface-well border border-border-hairline text-xs font-mono flex-shrink-0"
            >
              <button
                onClick={() => setShowRiskMetrics(false)}
                className={cn(
                  'px-3 py-1.5 rounded transition-colors cursor-pointer text-xs font-medium',
                  !showRiskMetrics
                    ? 'bg-brand-blue-soft text-brand-blue-text font-medium border border-brand-blue'
                    : 'text-zinc-400 hover:text-white border border-transparent'
                )}
              >
                Core View
              </button>
              <button
                onClick={() => setShowRiskMetrics(true)}
                className={cn(
                  'px-3 py-1.5 rounded transition-colors cursor-pointer text-xs font-medium',
                  showRiskMetrics
                    ? 'bg-brand-blue-soft text-brand-blue-text font-medium border border-brand-blue'
                    : 'text-zinc-400 hover:text-white border border-transparent'
                )}
              >
                Risk Stats
              </button>
            </div>
          </div>
        </div>

        <BenchmarkMatrixTable
          agents={filtered}
          navHistory={navHistory}
          isCompact={false}
          showRiskMetrics={showRiskMetrics}
        />
      </section>

      {/* 2. TRAJECTORY VISUALIZATION */}
      <section className="space-y-3">
        <SectionHeader
          title="Observed Return Curves"
          subtitle="Daily equity trajectories from initial seed capital against the NSE Nifty 500 index."
        />

        <AllAgentsReturnChart navHistory={navHistory} loading={loading} />
      </section>
    </div>
  );
}
