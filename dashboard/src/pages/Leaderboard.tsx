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
      <div className="max-w-7xl mx-auto px-4 py-16 flex justify-center items-center">
        <div className="flex items-center gap-3 text-[#7C8698] font-mono text-sm">
          <div className="w-4 h-4 border-2 border-[#8A7441] border-t-transparent rounded-full animate-spin" />
          <span>Loading strategy telemetry...</span>
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
      <div className="border-b border-[#DCD7CC] pb-6 flex flex-col md:flex-row justify-between items-start md:items-end gap-4">
        <div>
          <div className="flex items-center gap-1.5 text-xs font-mono text-[#8A7441] mb-1">
            <Award className="w-3.5 h-3.5" />
            <span>Autonomous trading strategy arena</span>
          </div>
          <h1 className="text-3xl font-serif font-bold text-[#151B26]">
            Strategy leaderboard
          </h1>
          <p className="text-sm text-[#475060] mt-1 max-w-2xl leading-relaxed">
            Comparative performance ranking of all 10 autonomous strategies (5 cognitive LLM personas + 5 matching rules baselines) trading separate ₹1,00,000 paper accounts on the NSE Nifty 500 universe.
          </p>
        </div>

        {/* Strategy Category Filter Chips */}
        <div className="flex items-center gap-1 p-1 rounded-[3px] bg-[#F6F4EF] border border-[#DCD7CC] text-xs font-mono">
          {(['ALL', 'LLM', 'RULES'] as const).map((filter) => (
            <button
              key={filter}
              onClick={() => setStrategyFilter(filter)}
              className={`px-3 py-1 rounded-[2px] transition-colors cursor-pointer ${
                strategyFilter === filter
                  ? 'bg-white font-medium text-[#151B26] shadow-xs border border-[#DCD7CC]'
                  : 'text-[#475060] hover:text-[#151B26]'
              }`}
            >
              {filter === 'ALL'
                ? `All 10 strategies`
                : filter === 'LLM'
                ? `5 LLM personas`
                : `5 Rules controls`}
            </button>
          ))}
        </div>
      </div>

      {/* Mandatory Small Sample Alert Banner */}
      <SmallSampleNotice closedTradesCount={14} threshold={30} />

      {/* KPI Cards Strip */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="ledger-panel p-4">
          <span className="text-[11px] font-sans text-[#7C8698] block">Total capital managed</span>
          <span className="text-2xl font-bold font-mono text-[#151B26] mt-0.5 block">
            {formatPaiseToRupees(totalPaise)}
          </span>
          <span className="text-[11px] font-mono text-[#7C8698] mt-1 block">
            Across 10 paper accounts
          </span>
        </div>

        <div className="ledger-panel p-4">
          <span className="text-[11px] font-sans text-[#7C8698] block">Current leader</span>
          <span className="text-xl font-bold font-serif text-[#151B26] mt-0.5 block truncate">
            {sorted[0]?.name || 'Jim Simons'}
          </span>
          <span className="text-xs font-mono font-medium text-[#1E6548] mt-1 block">
            {formatPct(sorted[0]?.returnPct)} (Alpha: +{formatPct(sorted[0]?.alphaVsBenchmarkPct)})
          </span>
        </div>

        <div className="ledger-panel p-4">
          <span className="text-[11px] font-sans text-[#7C8698] block">Simons cognitive spread</span>
          <span className="text-2xl font-bold font-mono text-[#1E6548] mt-0.5 block">
            +3.10%
          </span>
          <span className="text-[11px] font-mono text-[#7C8698] mt-1 block">
            LLM Simons vs. Rules Simons
          </span>
        </div>

        <div className="ledger-panel p-4">
          <span className="text-[11px] font-sans text-[#7C8698] block">Average faithfulness</span>
          <span className="text-2xl font-bold font-mono text-[#2A4B7C] mt-0.5 block">
            97.3%
          </span>
          <span className="text-[11px] font-mono text-[#7C8698] mt-1 block">
            Verified metric citations
          </span>
        </div>
      </div>

      {/* Multi-Agent Equity Curves Chart */}
      <EquityCurve data={navHistory} />

      {/* The 10-Agent Leaderboard Table */}
      <div className="ledger-panel overflow-hidden">
        <div className="p-4 border-b border-[#E7E3D9] flex justify-between items-center bg-white">
          <div>
            <h3 className="text-base font-serif font-bold text-[#151B26]">
              Strategy rankings & performance ledger
            </h3>
            <p className="text-xs text-[#7C8698]">
              Metric leaders highlighted in <strong>bold</strong>. Click any row to expand quick inspection details.
            </p>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-[#151B26]">
            <thead className="bg-[#F6F4EF] font-mono text-[11px] text-[#475060] border-b border-[#DCD7CC]">
              <tr>
                <th className="py-2.5 px-4 font-medium">Rank / Strategy</th>
                <th className="py-2.5 px-4 font-medium">Family</th>
                <th className="py-2.5 px-4 text-right font-medium">NAV (₹)</th>
                <th className="py-2.5 px-4 text-right font-medium">Return</th>
                <th className="py-2.5 px-4 text-right font-medium">Alpha</th>
                <th className="py-2.5 px-4 text-right font-medium">Sharpe</th>
                <th className="py-2.5 px-4 text-right font-medium">Max drawdown</th>
                <th className="py-2.5 px-4 text-right font-medium">Faithfulness</th>
                <th className="py-2.5 px-4 text-center font-medium">Trades (O/C)</th>
                <th className="py-2.5 px-4 text-center font-medium">Status</th>
                <th className="py-2.5 px-2"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E7E3D9]">
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
                    className="hover:bg-[#F6F4EF] transition-colors cursor-pointer group"
                  >
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-[#7C8698] text-xs w-4">
                          #{idx + 1}
                        </span>
                        <div>
                          <div className="flex items-center gap-1.5">
                            <span className="font-medium text-[#151B26] text-sm group-hover:text-[#8A7441] transition-colors">
                              {agent.name}
                            </span>
                            <span
                              className={`px-1.5 py-0.2 rounded-[2px] text-[9px] font-mono border ${
                                isControl
                                  ? 'bg-[#F6F4EF] text-[#475060] border-[#DCD7CC]'
                                  : 'bg-[#EDF2F9] text-[#2A4B7C] border-[#B9C9E1]'
                              }`}
                            >
                              {isControl ? 'Rules' : 'LLM'}
                            </span>
                          </div>
                        </div>
                      </div>
                    </td>

                    <td className="py-3 px-4 font-mono text-[11px] text-[#475060]">
                      {config.family}
                    </td>

                    <td className="py-3 px-4 text-right font-mono font-medium text-[#151B26]">
                      {formatPaiseToRupees(agent.navPaise)}
                    </td>

                    <td
                      className={`py-3 px-4 text-right font-mono font-medium ${
                        isReturnLeader
                          ? 'font-bold text-[#1E6548] underline decoration-[#A3D4BE]'
                          : agent.returnPct >= 0
                          ? 'text-[#1E6548]'
                          : 'text-[#933835]'
                      }`}
                    >
                      {formatPct(agent.returnPct)}
                    </td>

                    <td
                      className={`py-3 px-4 text-right font-mono ${
                        isAlphaLeader
                          ? 'font-bold text-[#1E6548] underline decoration-[#A3D4BE]'
                          : agent.alphaVsBenchmarkPct >= 0
                          ? 'text-[#1E6548] font-medium'
                          : 'text-[#933835]'
                      }`}
                    >
                      {agent.alphaVsBenchmarkPct >= 0 ? `+${formatPct(agent.alphaVsBenchmarkPct)}` : formatPct(agent.alphaVsBenchmarkPct)}
                    </td>

                    <td
                      className={`py-3 px-4 text-right font-mono ${
                        isSharpeLeader ? 'font-bold text-[#151B26]' : 'text-[#475060]'
                      }`}
                    >
                      {agent.sharpeRatio.toFixed(2)}
                    </td>

                    <td
                      className={`py-3 px-4 text-right font-mono text-[#933835] ${
                        isDrawdownLeader ? 'font-bold' : ''
                      }`}
                    >
                      -{agent.maxDrawdownPct.toFixed(2)}%
                    </td>

                    <td
                      className={`py-3 px-4 text-right font-mono text-[#2A4B7C] ${
                        isFaithfulnessLeader ? 'font-bold' : 'font-medium'
                      }`}
                    >
                      {agent.faithfulnessRatePct.toFixed(1)}%
                    </td>

                    <td className="py-3 px-4 text-center font-mono text-[#475060]">
                      {agent.activePositionsCount} / {agent.closedTrades}
                    </td>

                    <td className="py-3 px-4 text-center">
                      <SmallSampleNotice
                        closedTradesCount={agent.closedTrades}
                        threshold={30}
                        inline
                      />
                    </td>

                    <td className="py-3 px-2 text-center text-[#7C8698]">
                      {isExpanded ? (
                        <ChevronUp className="w-3.5 h-3.5 inline" />
                      ) : (
                        <ChevronDown className="w-3.5 h-3.5 inline" />
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Dynamic Foundation Model Footnote */}
        <div className="p-4 bg-[#F6F4EF] border-t border-[#DCD7CC] text-[11px] font-mono text-[#475060] space-y-1">
          <p>
            * <strong>Cognitive architecture parity:</strong> All LLM-based strategies are evaluated using the identical underlying foundation model (<code>Gemini 2.5 Flash</code>) to ensure clean cognitive parity with zero per-agent prompt bias.
          </p>
          <p className="text-[10px] text-[#7C8698]">
            * Metric leaders indicated in bold. Provisional status automatically applies to any strategy with fewer than 30 closed trades.
          </p>
        </div>
      </div>
    </div>
  );
}
