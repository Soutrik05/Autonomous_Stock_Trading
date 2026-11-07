import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  TrendingUp,
  Award,
  ShieldCheck,
  Scale,
  ArrowUpRight,
  ChevronRight,
  ExternalLink,
} from 'lucide-react';
import type { AgentLeaderboardEntry, NavHistoryPoint } from '../types';
import { apiService } from '../services/api';
import { formatPaiseToRupees, formatPct } from '../utils/formatters';
import EquityCurve from '../components/EquityCurve';
import SmallSampleNotice from '../components/SmallSampleNotice';

export default function Leaderboard() {
  const [agents, setAgents] = useState<AgentLeaderboardEntry[]>([]);
  const [navHistory, setNavHistory] = useState<NavHistoryPoint[]>([]);
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
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 flex justify-center items-center">
        <div className="flex items-center gap-3 text-stone-500 font-mono text-sm">
          <div className="w-4 h-4 border-2 border-amber-500 border-t-transparent rounded-full animate-spin" />
          <span>Loading leaderboard telemetry...</span>
        </div>
      </div>
    );
  }

  // Find top performer and control baseline
  const sorted = [...agents].sort((a, b) => b.returnPct - a.returnPct);
  const topAgent = sorted[0];
  const rulesBaseline = agents.find((a) => a.id === 'baseline-simons-rules');
  const simonsLlm = agents.find((a) => a.id === 'simons');
  const simonsAlphaOverRules =
    simonsLlm && rulesBaseline ? simonsLlm.returnPct - rulesBaseline.returnPct : 0;

  const totalPaiseManaged = agents.reduce((acc, a) => acc + a.navPaise, 0);
  const avgFaithfulness = (
    agents.reduce((acc, a) => acc + a.faithfulnessRatePct, 0) / (agents.length || 1)
  ).toFixed(1);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8 animate-fade-in">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-end gap-4 border-b border-stone-200 dark:border-stone-800 pb-6">
        <div>
          <div className="flex items-center gap-2 text-xs font-mono text-amber-600 dark:text-amber-400 uppercase tracking-wider mb-1">
            <Award className="w-3.5 h-3.5" />
            <span>Multi-Agent Paper Trading Arena</span>
          </div>
          <h1 className="text-3xl font-bold tracking-tight text-stone-900 dark:text-stone-100 font-serif">
            Strategy Leaderboard
          </h1>
          <p className="text-sm text-stone-500 dark:text-stone-400 mt-1 max-w-3xl">
            Live evaluation of five LLM investing personas against an independent rules-only control baseline and the Nifty 500 index. All trades are paper simulated with integer paise precision.
          </p>
        </div>

        <Link
          to="/comparison"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-amber-500 hover:bg-amber-600 text-white font-medium text-xs shadow-sm transition-all"
        >
          <span>Deep Baseline Analysis</span>
          <ArrowUpRight className="w-4 h-4" />
        </Link>
      </div>

      {/* Mandatory Small Sample Alert Banner */}
      <SmallSampleNotice closedTradesCount={simonsLlm?.closedTrades || 12} threshold={30} />

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-5 rounded-xl bg-white dark:bg-stone-900 border border-stone-200 dark:border-stone-800 shadow-xs">
          <div className="flex items-center justify-between text-xs text-stone-500 mb-2 font-mono">
            <span>TOTAL MANAGED CAPITAL</span>
            <TrendingUp className="w-4 h-4 text-amber-500" />
          </div>
          <div className="text-2xl font-bold font-mono text-stone-900 dark:text-stone-100">
            {formatPaiseToRupees(totalPaiseManaged)}
          </div>
          <div className="text-xs text-stone-400 mt-1 font-mono">
            6 independent ₹1,00,000 portfolios
          </div>
        </div>

        <div className="p-5 rounded-xl bg-white dark:bg-stone-900 border border-stone-200 dark:border-stone-800 shadow-xs">
          <div className="flex items-center justify-between text-xs text-stone-500 mb-2 font-mono">
            <span>LEADER (HIGHEST RETURN)</span>
            <Award className="w-4 h-4 text-emerald-500" />
          </div>
          <div className="text-xl font-bold font-mono text-emerald-600 dark:text-emerald-400 truncate">
            {topAgent?.name || 'Jim Simons'}
          </div>
          <div className="text-xs text-emerald-700/80 dark:text-emerald-300/80 mt-1 font-mono">
            {formatPct(topAgent?.returnPct)} (Alpha: {formatPct(topAgent?.alphaVsBenchmarkPct)})
          </div>
        </div>

        <div className="p-5 rounded-xl bg-white dark:bg-stone-900 border border-stone-200 dark:border-stone-800 shadow-xs">
          <div className="flex items-center justify-between text-xs text-stone-500 mb-2 font-mono">
            <span>LLM VS RULES ALPHA</span>
            <Scale className="w-4 h-4 text-blue-500" />
          </div>
          <div className="text-2xl font-bold font-mono text-blue-600 dark:text-blue-400">
            {formatPct(simonsAlphaOverRules)}
          </div>
          <div className="text-xs text-stone-400 mt-1 font-mono">
            Simons LLM ({formatPct(simonsLlm?.returnPct)}) vs Rules ({formatPct(rulesBaseline?.returnPct)})
          </div>
        </div>

        <div className="p-5 rounded-xl bg-white dark:bg-stone-900 border border-stone-200 dark:border-stone-800 shadow-xs">
          <div className="flex items-center justify-between text-xs text-stone-500 mb-2 font-mono">
            <span>AVG FAITHFULNESS</span>
            <ShieldCheck className="w-4 h-4 text-purple-500" />
          </div>
          <div className="text-2xl font-bold font-mono text-purple-600 dark:text-purple-400">
            {avgFaithfulness}%
          </div>
          <div className="text-xs text-stone-400 mt-1 font-mono">
            Cited metrics matched to snapshot
          </div>
        </div>
      </div>

      {/* Multi-Agent Equity Curves Chart */}
      <EquityCurve data={navHistory} />

      {/* Main Leaderboard Table */}
      <div className="bg-white dark:bg-stone-900 rounded-xl border border-stone-200 dark:border-stone-800 shadow-sm overflow-hidden">
        <div className="p-4 border-b border-stone-200 dark:border-stone-800 flex justify-between items-center">
          <div>
            <h3 className="text-base font-semibold text-stone-900 dark:text-stone-100">
              Agent Performance Table
            </h3>
            <p className="text-xs text-stone-500">
              Ranked by total Net Asset Value. Click any agent row to inspect full reasoning, trade forensics, and memory.
            </p>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-stone-700 dark:text-stone-300">
            <thead className="bg-stone-50 dark:bg-stone-800/60 uppercase font-semibold text-[11px] text-stone-500 dark:text-stone-400 tracking-wider">
              <tr>
                <th className="py-3 px-4">Rank / Agent</th>
                <th className="py-3 px-4">Investment Style</th>
                <th className="py-3 px-4 text-right">NAV (₹)</th>
                <th className="py-3 px-4 text-right">Return</th>
                <th className="py-3 px-4 text-right">Alpha</th>
                <th className="py-3 px-4 text-right">Sharpe</th>
                <th className="py-3 px-4 text-right">Max DD</th>
                <th className="py-3 px-4 text-right">Win Rate</th>
                <th className="py-3 px-4 text-right">Faithfulness</th>
                <th className="py-3 px-4 text-center">Trades (O/C)</th>
                <th className="py-3 px-4 text-center">Sample Status</th>
                <th className="py-3 px-2"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-stone-100 dark:divide-stone-800">
              {sorted.map((agent, idx) => {
                const isControl = agent.id === 'baseline-simons-rules';
                return (
                  <tr
                    key={agent.id}
                    className="hover:bg-stone-50/80 dark:hover:bg-stone-800/40 transition-colors group"
                  >
                    <td className="py-3.5 px-4">
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-bold text-stone-400 text-xs w-4">
                          #{idx + 1}
                        </span>
                        <div>
                          <Link
                            to={`/agents/${agent.id}`}
                            className="font-semibold text-stone-900 dark:text-stone-100 hover:text-amber-600 flex items-center gap-1 font-mono text-sm"
                          >
                            <span>{agent.name}</span>
                            <ExternalLink className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity" />
                          </Link>
                          {isControl && (
                            <span className="inline-block text-[10px] font-mono px-1.5 py-0.2 rounded bg-rose-100 text-rose-800 dark:bg-rose-950/60 dark:text-rose-300 font-semibold mt-0.5">
                              RULES CONTROL
                            </span>
                          )}
                        </div>
                      </div>
                    </td>

                    <td className="py-3.5 px-4">
                      <div className="text-stone-900 dark:text-stone-200 truncate max-w-[200px]">
                        {agent.philosophy}
                      </div>
                      <div className="text-[10px] text-stone-400 font-mono">
                        Target horizon: {agent.horizonDays}
                      </div>
                    </td>

                    <td className="py-3.5 px-4 text-right font-mono font-semibold text-stone-900 dark:text-stone-100">
                      {formatPaiseToRupees(agent.navPaise)}
                    </td>

                    <td
                      className={`py-3.5 px-4 text-right font-mono font-semibold ${
                        agent.returnPct >= 0
                          ? 'text-emerald-600 dark:text-emerald-400'
                          : 'text-rose-600 dark:text-rose-400'
                      }`}
                    >
                      {formatPct(agent.returnPct)}
                    </td>

                    <td
                      className={`py-3.5 px-4 text-right font-mono ${
                        agent.alphaVsBenchmarkPct >= 0
                          ? 'text-emerald-600 dark:text-emerald-400'
                          : 'text-rose-600 dark:text-rose-400'
                      }`}
                    >
                      {formatPct(agent.alphaVsBenchmarkPct)}
                    </td>

                    <td className="py-3.5 px-4 text-right font-mono">
                      {agent.sharpeRatio.toFixed(2)}
                    </td>

                    <td className="py-3.5 px-4 text-right font-mono text-rose-600 dark:text-rose-400">
                      -{agent.maxDrawdownPct.toFixed(2)}%
                    </td>

                    <td className="py-3.5 px-4 text-right font-mono">
                      {agent.winRatePct.toFixed(1)}%
                    </td>

                    <td className="py-3.5 px-4 text-right font-mono text-purple-600 dark:text-purple-400 font-medium">
                      {agent.faithfulnessRatePct.toFixed(1)}%
                    </td>

                    <td className="py-3.5 px-4 text-center font-mono">
                      {agent.activePositionsCount} / {agent.closedTrades}
                    </td>

                    <td className="py-3.5 px-4 text-center">
                      <SmallSampleNotice
                        closedTradesCount={agent.closedTrades}
                        threshold={30}
                        inline
                      />
                    </td>

                    <td className="py-3.5 px-2 text-right">
                      <Link
                        to={`/agents/${agent.id}`}
                        className="p-1 rounded text-stone-400 hover:text-stone-700 dark:hover:text-stone-200 inline-block"
                        title="View agent cockpit"
                      >
                        <ChevronRight className="w-4 h-4" />
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Persona Philosophy Reference Cards */}
      <div className="border-t border-stone-200 dark:border-stone-800 pt-6">
        <h3 className="text-lg font-semibold text-stone-900 dark:text-stone-100 font-serif mb-4">
          Investing Personas & Philosophy Architectures
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[
            {
              id: 'simons',
              name: 'Jim Simons',
              style: 'Quantitative Momentum',
              horizon: '5–15 days',
              rules: 'Kaufman ER > 0.60, ADX 14 > 25, Volatility Parity sizing, 1.5 ATR Trailing Stop.',
            },
            {
              id: 'lynch',
              name: 'Peter Lynch',
              style: 'Growth at Reasonable Price (GARP)',
              horizon: '60–120 days',
              rules: 'PEG < 1.0, ROCE > 15%, CFO/PAT > 0.80, avoids high institutional ownership.',
            },
            {
              id: 'marks',
              name: 'Howard Marks',
              style: 'Contrarian Value & Second-Level Thinking',
              horizon: '30–90 days',
              rules: 'P/E in lowest 30% of 5y range, debt/equity < 0.5, distinguishes temporary cyclical panics from fatal traps.',
            },
            {
              id: 'jhunjhunwala',
              name: 'Rakesh Jhunjhunwala',
              style: 'Structural Growth & Promoter Quality',
              horizon: '90–180 days',
              rules: 'High promoter pledge check (= 0), secular domestic demand expansion, high conviction pyramiding.',
            },
            {
              id: 'stockminds-core',
              name: 'Zerodha Varsity Balanced',
              style: 'Dual Confluence & DCF Valuation',
              horizon: '20–60 days',
              rules: 'Dual confluence technical confirmation + DCF intrinsic FCFF valuation clamp and fractional Kelly sizing.',
            },
            {
              id: 'baseline-simons-rules',
              name: 'Simons (Rules Baseline)',
              style: 'Deterministic Control Agent',
              horizon: '5–15 days',
              rules: 'Executes identical Stage 1–3 quantitative filters without LLM inference to isolate cognitive alpha.',
            },
          ].map((persona) => (
            <div
              key={persona.id}
              className="p-4 rounded-xl border border-stone-200 dark:border-stone-800 bg-white dark:bg-stone-900 text-xs space-y-2"
            >
              <div className="flex justify-between items-center">
                <span className="font-semibold text-sm text-stone-900 dark:text-stone-100">
                  {persona.name}
                </span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-stone-100 dark:bg-stone-800 text-stone-600 dark:text-stone-400">
                  {persona.horizon}
                </span>
              </div>
              <div className="font-medium text-amber-600 dark:text-amber-400">
                {persona.style}
              </div>
              <p className="text-stone-500 dark:text-stone-400 leading-relaxed">
                {persona.rules}
              </p>
              <div className="pt-2">
                <Link
                  to={`/agents/${persona.id}`}
                  className="text-stone-700 dark:text-stone-300 hover:text-amber-600 font-semibold flex items-center gap-1 font-mono text-[11px]"
                >
                  <span>Open cockpit</span>
                  <ChevronRight className="w-3 h-3" />
                </Link>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
