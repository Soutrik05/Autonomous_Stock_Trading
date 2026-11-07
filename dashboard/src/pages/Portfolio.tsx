import { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  Briefcase,
  ListOrdered,
  Brain,
  Layers,
  ArrowLeft,
  History,
} from 'lucide-react';
import type {
  AgentId,
  AgentLeaderboardEntry,
  Position,
  Order,
  Decision,
  HeuristicMemory,
} from '../types';
import { apiService } from '../services/api';
import { formatPaiseToRupees, formatPct, formatISTDateTime } from '../utils/formatters';
import PositionTable from '../components/PositionTable';
import SmallSampleNotice from '../components/SmallSampleNotice';
import { STRATEGY_THEME } from '../theme/tokens';

const AGENT_LIST = [
  { id: 'simons', name: 'Jim Simons (LLM)' },
  { id: 'lynch', name: 'Peter Lynch' },
  { id: 'marks', name: 'Howard Marks' },
  { id: 'jhunjhunwala', name: 'Rakesh Jhunjhunwala' },
  { id: 'stockminds-core', name: 'StockMinds Core (Varsity)' },
  { id: 'baseline-simons-rules', name: 'Simons (Rules Baseline)' },
];

export default function Portfolio() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const currentAgentId = (id as AgentId) || 'simons';

  const [agent, setAgent] = useState<AgentLeaderboardEntry | null>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [heuristics, setHeuristics] = useState<HeuristicMemory[]>([]);
  const [activeTab, setActiveTab] = useState<'active' | 'past' | 'orders' | 'decisions' | 'heuristics'>('active');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      setLoading(true);
      try {
        const [allAgents, posData, orderData, decData, memData] = await Promise.all([
          apiService.getLeaderboard(),
          apiService.getAgentPositions(currentAgentId),
          apiService.getAgentOrders(currentAgentId),
          apiService.getAgentDecisions(currentAgentId),
          apiService.getAgentMemory(currentAgentId),
        ]);

        const current = allAgents.find((a) => a.id === currentAgentId) || allAgents[0] || null;
        setAgent(current);
        setPositions(posData);
        setOrders(orderData);
        setDecisions(decData);
        setHeuristics(memData);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, [currentAgentId]);

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-24 flex justify-center items-center">
        <div className="flex items-center gap-3 text-slate-400 font-mono text-sm">
          <div className="w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
          <span>Loading agent portfolio...</span>
        </div>
      </div>
    );
  }

  const activePositions = positions.filter((p) => p.status === 'OPEN');
  const closedPositions = positions.filter((p) => p.status === 'CLOSED');

  const investedPaise = activePositions.reduce((acc, p) => acc + p.quantity * p.entryPricePaise, 0);
  const cashPaise = (agent?.navPaise || 10000000) - investedPaise;
  const config = STRATEGY_THEME[currentAgentId] || STRATEGY_THEME.simons;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6 animate-fade-in font-sans">
      {/* Top Bar Navigation */}
      <div className="flex items-center justify-between">
        <Link
          to="/leaderboard"
          className="inline-flex items-center gap-2 text-xs font-mono text-slate-400 hover:text-white transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Strategy Leaderboard</span>
        </Link>

        {/* Strategy Switcher */}
        <div className="flex items-center gap-2 text-xs font-mono">
          <span className="text-slate-500 hidden sm:inline">Active Strategy:</span>
          <select
            value={currentAgentId}
            onChange={(e) => navigate(`/portfolio/${e.target.value}`)}
            className="bg-[#090B10] border border-white/10 text-white rounded px-3 py-1.5 font-mono text-xs cursor-pointer focus:ring-1 focus:ring-blue-500"
          >
            {AGENT_LIST.map((ag) => (
              <option key={ag.id} value={ag.id}>
                {ag.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Hero Identity Banner */}
      <div className="arena-glass p-6 sm:p-7 space-y-4">
        <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-6">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2.5">
              <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white">
                {agent?.name || currentAgentId}
              </h1>
              <span
                className={`px-2.5 py-0.5 rounded text-[10px] font-mono border ${
                  config.badge === 'RULES'
                    ? 'bg-white/5 text-slate-400 border-white/10'
                    : 'bg-blue-500/15 text-blue-300 border-blue-500/30'
                }`}
              >
                {config.badge === 'RULES' ? 'Rules Control' : 'LLM Persona'}
              </span>
            </div>

            <p className="text-xs sm:text-sm text-slate-400 max-w-2xl leading-relaxed">
              {agent?.philosophy}
            </p>

            <div className="flex flex-wrap items-center gap-4 text-xs font-mono text-slate-500 pt-1">
              <span>Family: <strong className="text-white">{config.family}</strong></span>
              <span>·</span>
              <span>Universe: <strong className="text-white">NSE Nifty 500</strong></span>
              <span>·</span>
              <span>Metric Faithfulness: <strong className="text-purple-400">{agent?.faithfulnessRatePct.toFixed(1)}%</strong></span>
            </div>
          </div>

          {/* Capital Matrix Inset */}
          <div className="arena-glass-subdued p-5 rounded-xl border border-white/10 flex items-center gap-6 font-mono text-xs">
            <div>
              <div className="text-[10px] text-slate-500 uppercase">Portfolio NAV</div>
              <div className="text-xl font-bold text-white mt-0.5">
                {formatPaiseToRupees(agent?.navPaise)}
              </div>
              <div className={`text-[11px] font-semibold mt-0.5 ${(agent?.returnPct || 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                {formatPct(agent?.returnPct)} (Alpha: +{formatPct(agent?.alphaVsBenchmarkPct)})
              </div>
            </div>

            <div className="h-10 w-px bg-white/10" />

            <div className="space-y-1 text-[11px]">
              <div>
                <span className="text-slate-500">Available Cash: </span>
                <span className="font-semibold text-white">{formatPaiseToRupees(cashPaise)}</span>
              </div>
              <div>
                <span className="text-slate-500">Invested Equity: </span>
                <span className="font-semibold text-white">{formatPaiseToRupees(investedPaise)}</span>
              </div>
              <div>
                <span className="text-slate-500">Open Positions: </span>
                <span className="font-semibold text-white">{activePositions.length} stocks</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Small Sample Warning */}
      <SmallSampleNotice closedTradesCount={agent?.closedTrades || 0} threshold={30} />

      {/* Segmented Navigation Tabs */}
      <div className="flex border-b border-white/10 space-x-6 text-xs font-mono font-medium overflow-x-auto">
        {[
          { key: 'active', label: 'Active Positions', count: activePositions.length, icon: Briefcase },
          { key: 'past', label: 'Past Trades Ledger', count: closedPositions.length, icon: History },
          { key: 'orders', label: 'Broker Orders', count: orders.length, icon: ListOrdered },
          { key: 'decisions', label: 'Decisions Audit', count: decisions.length, icon: Brain },
          { key: 'heuristics', label: 'Heuristic Memory', count: heuristics.length, icon: Layers },
        ].map(({ key, label, count, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setActiveTab(key as typeof activeTab)}
            className={`pb-3.5 flex items-center gap-2 border-b-2 transition-all cursor-pointer whitespace-nowrap ${
              activeTab === key
                ? 'border-blue-500 text-white font-semibold'
                : 'border-transparent text-slate-400 hover:text-white'
            }`}
          >
            <Icon className="w-4 h-4 text-blue-400" />
            <span>{label}</span>
            <span className="px-2 py-0.5 rounded-full text-[10px] bg-white/[0.04] text-slate-400 border border-white/10">
              {count}
            </span>
          </button>
        ))}
      </div>

      {/* TAB CONTENT */}
      {activeTab === 'active' && (
        <PositionTable
          positions={activePositions}
          title="Active Positions (Current Holdings)"
          defaultStatus="OPEN"
        />
      )}

      {activeTab === 'past' && (
        <PositionTable
          positions={closedPositions}
          title="Historical Trade Log & Forensics Ledger"
          defaultStatus="CLOSED"
        />
      )}

      {activeTab === 'orders' && (
        <div className="arena-glass overflow-hidden shadow-2xl">
          <div className="p-5 border-b border-white/10 bg-white/[0.02]">
            <h3 className="text-base font-bold text-white">
              Broker Execution & Audit Log
            </h3>
            <p className="text-xs text-slate-400">
              Limit orders matched against daily OHLCV bands. Unfilled orders expire daily at 15:30 IST.
            </p>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono text-slate-200">
              <thead className="bg-white/[0.02] text-[11px] text-slate-400 border-b border-white/10">
                <tr>
                  <th className="py-3 px-4 font-semibold">Order ID</th>
                  <th className="py-3 px-4 font-semibold">Symbol</th>
                  <th className="py-3 px-4 font-semibold">Side / Type</th>
                  <th className="py-3 px-4 text-right font-semibold">Quantity</th>
                  <th className="py-3 px-4 text-right font-semibold">Limit Price</th>
                  <th className="py-3 px-4 text-right font-semibold">Filled Price</th>
                  <th className="py-3 px-4 font-semibold">Status</th>
                  <th className="py-3 px-4 text-right font-semibold">Charges</th>
                  <th className="py-3 px-4 font-semibold">Submitted (IST)</th>
                  <th className="py-3 px-4 font-semibold">Notes / Rejection Reason</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {orders.map((ord) => (
                  <tr key={ord.id} className="hover:bg-white/[0.04] transition-colors">
                    <td className="py-3 px-4 text-slate-500">#{ord.id}</td>
                    <td className="py-3 px-4 font-bold text-white">{ord.symbol}</td>
                    <td className="py-3 px-4">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-semibold border ${ord.side === 'BUY' ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' : 'bg-rose-500/15 text-rose-400 border-rose-500/30'}`}>
                        {ord.side}
                      </span>{' '}
                      <span className="text-slate-500 text-[10px]">{ord.orderType}</span>
                    </td>
                    <td className="py-3 px-4 text-right text-white font-medium">{ord.quantity}</td>
                    <td className="py-3 px-4 text-right text-slate-400">{formatPaiseToRupees(ord.limitPricePaise)}</td>
                    <td className="py-3 px-4 text-right text-white font-semibold">
                      {ord.filledPricePaise ? formatPaiseToRupees(ord.filledPricePaise) : '-'}
                    </td>
                    <td className="py-3 px-4">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-semibold border ${
                        ord.status === 'FILLED' ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' :
                        ord.status === 'EXPIRED' ? 'bg-amber-500/15 text-amber-400 border-amber-500/30' :
                        ord.status === 'REJECTED' ? 'bg-rose-500/15 text-rose-400 border-rose-500/30' : 'bg-white/5 text-slate-400 border-white/10'
                      }`}>
                        {ord.status}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right text-slate-400">
                      {formatPaiseToRupees(ord.statutoryChargesPaise)}
                    </td>
                    <td className="py-3 px-4 text-[11px] text-slate-400">
                      {formatISTDateTime(ord.submittedAt)}
                    </td>
                    <td className="py-3 px-4 text-slate-400 text-[11px] truncate max-w-xs font-sans">
                      {ord.rejectionReason || 'Filled with standard statutory charges.'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {activeTab === 'decisions' && (
        <div className="space-y-4">
          <div className="arena-glass p-5">
            <h3 className="font-bold text-base text-white">
              Decision Faithfulness & Verbatim Rationale Inspector
            </h3>
            <p className="text-xs text-slate-400">
              Every metric citation is deterministically checked against the saved market snapshot.
            </p>
          </div>

          {decisions.map((dec) => (
            <div key={dec.id} className="arena-glass p-5 space-y-3">
              <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2 border-b border-white/10 pb-3">
                <div className="flex items-center gap-2.5">
                  <span className={`px-2.5 py-0.5 rounded text-xs font-mono font-medium border ${
                    dec.action === 'BUY' ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' : 'bg-white/5 text-slate-400 border-white/10'
                  }`}>
                    {dec.action} {dec.symbol}
                  </span>
                  <span className="text-xs font-mono text-slate-500">
                    Date: {dec.decisionDate}
                  </span>
                </div>

                <div className="text-xs font-mono text-purple-300 bg-purple-500/15 px-2.5 py-0.5 rounded border border-purple-500/30">
                  Faithfulness: {(dec.faithfulnessScore * 100).toFixed(0)}%
                </div>
              </div>

              <div className="p-4 rounded-xl bg-black/40 text-xs text-slate-200 leading-relaxed italic border border-white/10">
                "{dec.rationale}"
              </div>

              {/* Cited Metrics Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 pt-1 font-mono text-xs">
                {dec.citedMetrics.map((cm, i) => (
                  <div key={i} className="p-3 rounded-lg border border-white/10 bg-black/30 flex justify-between items-center">
                    <div>
                      <span className="text-[11px] text-slate-500 block">{cm.name}</span>
                      <span className="font-semibold text-white">
                        Cited: {cm.citedValue} <span className="text-slate-500 font-normal">(Truth: {cm.actualSnapshotValue})</span>
                      </span>
                    </div>
                    <span className="text-emerald-400 font-bold text-xs">✓</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {activeTab === 'heuristics' && (
        <div className="space-y-4">
          <div className="arena-glass p-5">
            <h3 className="font-bold text-base text-white">
              Causal Forensics & Heuristic Memory Bank
            </h3>
            <p className="text-xs text-slate-400">
              Machine-checkable rules extracted by the weekly reflection loop from closed trade post-mortems.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {heuristics.map((h) => (
              <div key={h.id} className="arena-glass p-5 space-y-3">
                <div className="flex justify-between items-center text-xs font-mono">
                  <span className={`px-2 py-0.5 rounded font-semibold border ${
                    h.kind === 'AVOID' ? 'bg-rose-500/15 text-rose-400 border-rose-500/30' : 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                  }`}>
                    {h.kind}
                  </span>
                  <span className="px-2 py-0.5 rounded bg-white/5 text-slate-400 font-medium border border-white/10">
                    {h.status}
                  </span>
                </div>

                <p className="text-xs font-medium text-slate-200 leading-relaxed font-sans">
                  {h.ruleDescription}
                </p>

                <div className="flex justify-between items-center text-xs font-mono text-slate-500 pt-3 border-t border-white/10">
                  <span>Confidence: <strong className="text-white">{(h.confidenceScore * 100).toFixed(0)}%</strong></span>
                  <span>Tested: <strong className="text-white">{h.timesApplied}x ({h.successRatePct.toFixed(0)}% win)</strong></span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
