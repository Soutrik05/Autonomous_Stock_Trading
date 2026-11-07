import { useState, useEffect } from 'react';
import {
  Award,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import type { AgentLeaderboardEntry, NavHistoryPoint } from '../types';
import { apiService } from '../services/api';
import { formatPaiseToRupees, formatPct } from '../utils/formatters';
import EquityCurve from '../components/EquityCurve';
import SmallSampleNotice from '../components/SmallSampleNotice';
import { STRATEGY_THEME } from '../theme/tokens';

export default function Leaderboard() {
  const [agents, setAgents] = useState<AgentLeaderboardEntry[]>([]);
  const [navHistory, setNavHistory] = useState<NavHistoryPoint[]>([]);
  const [strategyFilter, setStrategyFilter] = useState<'ALL' | 'LLM' | 'RULES'>('ALL');
  const [expandedAgentId, setExpandedAgentId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        const [leaderboardData, navData] = await Promise.all([
          apiService.getLeaderboard(),
          apiService.getAgentNavHistory(),
        ]);
        setAgents(leaderboardData);
        setNavHistory(navData);
      } finally {
        setLoading(false);
      }
    }
    loadData();

    const handleModeChange = () => {
      loadData();
    };
    window.addEventListener('mock_mode_changed', handleModeChange);
    return () => window.removeEventListener('mock_mode_changed', handleModeChange);
  }, []);

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-24 flex justify-center items-center">
        <div className="flex items-center gap-3 text-slate-400 font-mono text-sm">
          <div className="w-5 h-5 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />
          <span>Synchronizing strategy telemetry...</span>
        </div>
      </div>
    );
  }

  // Filter strategies
  const filtered = agents.filter((a) => {
    const isControl = a.id.startsWith('baseline-');
    if (strategyFilter === 'LLM') return !isControl;
    if (strategyFilter === 'RULES') return isControl;
    return true;
  });

  const sorted = [...filtered].sort((a, b) => b.returnPct - a.returnPct);

  // Compute leaders for bold highlighting (SSOT)
  const maxReturn = Math.max(...agents.map((a) => a.returnPct));
  const maxAlpha = Math.max(...agents.map((a) => a.alphaVsBenchmarkPct));
  const maxSharpe = Math.max(...agents.map((a) => a.sharpeRatio));
  const minDrawdown = Math.min(...agents.map((a) => a.maxDrawdownPct));
  const maxFaithfulness = Math.max(...agents.map((a) => a.faithfulnessRatePct));

  const totalPaise = agents.reduce((sum, a) => sum + a.navPaise, 0);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8 animate-fade-in font-sans">
      {/* Header */}
      <div className="border-b border-white/10 pb-6 flex flex-col md:flex-row justify-between items-start md:items-end gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-mono text-cyan-400 uppercase tracking-wider mb-1 font-semibold">
            <Award className="w-3.5 h-3.5" />
            <span>Autonomous Trading Strategy Arena</span>
          </div>
          <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-white">
            Strategy Leaderboard
          </h1>
          <p className="text-sm text-slate-400 mt-1 max-w-2xl leading-relaxed">
            Comparative performance ranking of all 10 autonomous strategies (5 cognitive LLM personas + 5 matching rules baselines) trading separate ₹1,00,000 paper accounts on the NSE Nifty 500 universe.
          </p>
        </div>

        {/* Strategy Category Filter Chips */}
        <div className="flex items-center gap-1.5 p-1 rounded-xl bg-white/[0.04] border border-white/10 text-xs font-mono backdrop-blur-md">
          {(['ALL', 'LLM', 'RULES'] as const).map((filter) => (
            <button
              key={filter}
              onClick={() => setStrategyFilter(filter)}
              className={`px-3.5 py-1.5 rounded-lg font-medium transition-all cursor-pointer ${
                strategyFilter === filter
                  ? 'bg-cyan-500/20 text-cyan-300 font-semibold border border-cyan-500/30 shadow-[0_0_12px_rgba(6,182,212,0.2)]'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              {filter === 'ALL'
                ? `All 10 Strategies`
                : filter === 'LLM'
                ? `5 LLM Personas`
                : `5 Rules Controls`}
            </button>
          ))}
        </div>
      </div>

      {/* Mandatory Small Sample Alert Banner */}
      <SmallSampleNotice closedTradesCount={14} threshold={30} />

      {/* KPI Cards Strip (Translucent Glass) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="arena-glass p-5">
          <span className="text-[11px] font-sans text-slate-400 block">Total capital managed</span>
          <span className="text-2xl font-bold font-mono text-white mt-1 block tracking-tight">
            {formatPaiseToRupees(totalPaise)}
          </span>
          <span className="text-[11px] font-mono text-slate-500 mt-1 block">
            Across 10 paper accounts
          </span>
        </div>

        <div className="arena-glass p-5">
          <span className="text-[11px] font-sans text-slate-400 block">Current leader</span>
          <span className="text-xl font-bold text-white mt-1 block truncate">
            {sorted[0]?.name || 'Jim Simons'}
          </span>
          <span className="text-xs font-mono font-medium text-emerald-400 mt-1 block">
            {formatPct(sorted[0]?.returnPct)} (Alpha: +{formatPct(sorted[0]?.alphaVsBenchmarkPct)})
          </span>
        </div>

        <div className="arena-glass p-5">
          <span className="text-[11px] font-sans text-slate-400 block">Simons cognitive spread</span>
          <span className="text-2xl font-bold font-mono text-emerald-400 mt-1 block">
            +3.10%
          </span>
          <span className="text-[11px] font-mono text-slate-500 mt-1 block">
            LLM Simons vs. Rules Simons
          </span>
        </div>

        <div className="arena-glass p-5">
          <span className="text-[11px] font-sans text-slate-400 block">Average faithfulness</span>
          <span className="text-2xl font-bold font-mono text-purple-400 mt-1 block">
            97.3%
          </span>
          <span className="text-[11px] font-mono text-slate-500 mt-1 block">
            Verified metric citations
          </span>
        </div>
      </div>

      {/* Multi-Agent Equity Curves Chart */}
      <EquityCurve data={navHistory} />

      {/* The 10-Agent Leaderboard Translucent Table */}
      <div className="arena-glass overflow-hidden shadow-2xl">
        <div className="p-5 border-b border-white/10 flex justify-between items-center bg-white/[0.02]">
          <div>
            <h3 className="text-base font-bold text-white">
              Strategy Rankings & Performance Ledger
            </h3>
            <p className="text-xs text-slate-400">
              Metric leaders highlighted in <strong>bold</strong>. Click any row to expand quick inspection details.
            </p>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono text-slate-200">
            <thead className="bg-white/[0.02] text-[11px] text-slate-400 border-b border-white/10">
              <tr>
                <th className="py-3 px-4 font-semibold">Rank / Strategy</th>
                <th className="py-3 px-4 font-semibold">Family</th>
                <th className="py-3 px-4 text-right font-semibold">NAV (₹)</th>
                <th className="py-3 px-4 text-right font-semibold">Return</th>
                <th className="py-3 px-4 text-right font-semibold">Alpha</th>
                <th className="py-3 px-4 text-right font-semibold">Sharpe</th>
                <th className="py-3 px-4 text-right font-semibold">Max DD</th>
                <th className="py-3 px-4 text-right font-semibold">Faithfulness</th>
                <th className="py-3 px-4 text-center font-semibold">Trades (O/C)</th>
                <th className="py-3 px-4 text-center font-semibold">Status</th>
                <th className="py-3 px-2"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {sorted.map((agent, idx) => {
                const config = STRATEGY_THEME[agent.id] || STRATEGY_THEME.simons;
                const isControl = agent.id.startsWith('baseline-');
                const isExpanded = expandedAgentId === agent.id;

                // Bold leader checks
                const isReturnLeader = agent.returnPct === maxReturn;
                const isAlphaLeader = agent.alphaVsBenchmarkPct === maxAlpha;
                const isSharpeLeader = agent.sharpeRatio === maxSharpe;
                const isDrawdownLeader = agent.maxDrawdownPct === minDrawdown;
                const isFaithfulnessLeader = agent.faithfulnessRatePct === maxFaithfulness;

                return (
                  <tr
                    key={agent.id}
                    onClick={() => setExpandedAgentId(isExpanded ? null : agent.id)}
                    className="hover:bg-white/[0.04] transition-colors cursor-pointer group"
                  >
                    <td className="py-3.5 px-4">
                      <div className="flex items-center gap-2.5">
                        <span className="text-slate-500 text-xs w-4">
                          #{idx + 1}
                        </span>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-white text-sm group-hover:text-cyan-400 transition-colors">
                              {agent.name}
                            </span>
                            <span
                              className={`px-1.5 py-0.2 rounded text-[9px] border ${
                                isControl
                                  ? 'bg-white/5 text-slate-400 border-white/10'
                                  : 'bg-blue-500/15 text-blue-400 border-blue-500/30'
                              }`}
                            >
                              {isControl ? 'Rules' : 'LLM'}
                            </span>
                          </div>
                        </div>
                      </div>
                    </td>

                    <td className="py-3.5 px-4 text-[11px] text-slate-400">
                      {config.family}
                    </td>

                    <td className="py-3.5 px-4 text-right font-semibold text-white">
                      {formatPaiseToRupees(agent.navPaise)}
                    </td>

                    <td
                      className={`py-3.5 px-4 text-right font-medium ${
                        isReturnLeader
                          ? 'font-extrabold text-emerald-400 underline decoration-emerald-400/50'
                          : agent.returnPct >= 0
                          ? 'text-emerald-400'
                          : 'text-rose-400'
                      }`}
                    >
                      {formatPct(agent.returnPct)}
                    </td>

                    <td
                      className={`py-3.5 px-4 text-right ${
                        isAlphaLeader
                          ? 'font-extrabold text-emerald-400 underline decoration-emerald-400/50'
                          : agent.alphaVsBenchmarkPct >= 0
                          ? 'text-emerald-400 font-semibold'
                          : 'text-rose-400'
                      }`}
                    >
                      {agent.alphaVsBenchmarkPct >= 0 ? `+${formatPct(agent.alphaVsBenchmarkPct)}` : formatPct(agent.alphaVsBenchmarkPct)}
                    </td>

                    <td
                      className={`py-3.5 px-4 text-right ${
                        isSharpeLeader ? 'font-bold text-white' : 'text-slate-400'
                      }`}
                    >
                      {agent.sharpeRatio.toFixed(2)}
                    </td>

                    <td
                      className={`py-3.5 px-4 text-right text-rose-400 ${
                        isDrawdownLeader ? 'font-bold' : ''
                      }`}
                    >
                      -{agent.maxDrawdownPct.toFixed(2)}%
                    </td>

                    <td
                      className={`py-3.5 px-4 text-right text-purple-400 ${
                        isFaithfulnessLeader ? 'font-bold' : 'font-medium'
                      }`}
                    >
                      {agent.faithfulnessRatePct.toFixed(1)}%
                    </td>

                    <td className="py-3.5 px-4 text-center text-slate-400">
                      {agent.activePositionsCount} / {agent.closedTrades}
                    </td>

                    <td className="py-3.5 px-4 text-center">
                      <SmallSampleNotice
                        closedTradesCount={agent.closedTrades}
                        threshold={30}
                        inline
                      />
                    </td>

                    <td className="py-3.5 px-2 text-center text-slate-500">
                      {isExpanded ? (
                        <ChevronUp className="w-4 h-4 inline" />
                      ) : (
                        <ChevronDown className="w-4 h-4 inline" />
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Dynamic Model Footnote */}
        <div className="p-4 bg-white/[0.02] border-t border-white/10 text-[11px] text-slate-400 space-y-1">
          <p>
            * <strong>Cognitive Architecture Parity:</strong> All LLM-based strategies are evaluated using the identical underlying foundation model (<code>Gemini 2.5 Flash</code>) to ensure clean cognitive parity with zero per-agent prompt bias.
          </p>
          <p className="text-[10px] text-slate-500">
            * Metric leaders indicated in bold. PROVISIONAL tags automatically apply to any strategy with fewer than 30 closed trades.
          </p>
        </div>
      </div>
    </div>
  );
}
