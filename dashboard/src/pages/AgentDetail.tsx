import { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  ShieldCheck,
  Brain,
  ListOrdered,
  Briefcase,
  Layers,
  CheckCircle2,
  XCircle,
  ArrowLeft,
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
import {
  formatPaiseToRupees,
  formatPct,
  formatISTDateTime,
} from '../utils/formatters';
import PositionTable from '../components/PositionTable';
import SmallSampleNotice from '../components/SmallSampleNotice';

const AGENT_NAMES: Record<AgentId, string> = {
  simons: 'Jim Simons (LLM)',
  lynch: 'Peter Lynch',
  marks: 'Howard Marks',
  jhunjhunwala: 'Rakesh Jhunjhunwala',
  'stockminds-core': 'StockMinds Core (Varsity)',
  'baseline-simons-rules': 'Simons (Rules Baseline)',
};

export default function AgentDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const currentAgentId = (id as AgentId) || 'simons';

  const [agent, setAgent] = useState<AgentLeaderboardEntry | null>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [heuristics, setHeuristics] = useState<HeuristicMemory[]>([]);
  const [activeTab, setActiveTab] = useState<'positions' | 'orders' | 'decisions' | 'heuristics'>('positions');
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

        const current = allAgents.find((a) => a.id === currentAgentId) || null;
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
      <div className="max-w-7xl mx-auto px-4 py-12 flex justify-center items-center">
        <div className="flex items-center gap-3 text-stone-500 font-mono text-sm">
          <div className="w-4 h-4 border-2 border-amber-500 border-t-transparent rounded-full animate-spin" />
          <span>Loading agent telemetry...</span>
        </div>
      </div>
    );
  }

  const investedPaise = positions
    .filter((p) => p.status === 'OPEN')
    .reduce((sum, p) => sum + p.quantity * p.entryPricePaise, 0);
  const cashPaise = (agent?.navPaise || 10000000) - investedPaise;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6 animate-fade-in">
      {/* Back to Leaderboard */}
      <div className="flex items-center justify-between">
        <Link
          to="/"
          className="inline-flex items-center gap-1.5 text-xs font-mono text-stone-500 hover:text-stone-900 dark:hover:text-stone-100 transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Strategy Leaderboard</span>
        </Link>

        {/* Quick Agent Switcher */}
        <div className="flex items-center gap-1 text-xs">
          <span className="text-stone-400 font-mono hidden sm:inline">Switch Cockpit:</span>
          <select
            value={currentAgentId}
            onChange={(e) => navigate(`/agents/${e.target.value}`)}
            className="bg-white dark:bg-stone-900 border border-stone-200 dark:border-stone-800 text-stone-800 dark:text-stone-200 rounded-lg px-2.5 py-1 text-xs font-mono focus:outline-hidden focus:ring-1 focus:ring-amber-500"
          >
            {Object.entries(AGENT_NAMES).map(([aid, name]) => (
              <option key={aid} value={aid}>
                {name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Hero Header Card */}
      <div className="bg-white dark:bg-stone-900 rounded-xl border border-stone-200 dark:border-stone-800 p-6 shadow-sm">
        <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-6">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold font-serif text-stone-900 dark:text-stone-100">
                {agent?.name || currentAgentId}
              </h1>
              {agent?.id === 'baseline-simons-rules' ? (
                <span className="text-xs px-2 py-0.5 rounded font-mono font-semibold bg-rose-100 text-rose-800 dark:bg-rose-950/60 dark:text-rose-300">
                  RULES CONTROL
                </span>
              ) : (
                <span className="text-xs px-2 py-0.5 rounded font-mono font-semibold bg-blue-100 text-blue-800 dark:bg-blue-950/60 dark:text-blue-300">
                  LLM REASONING LAYER
                </span>
              )}
            </div>
            <p className="text-sm text-stone-600 dark:text-stone-400 max-w-2xl leading-relaxed">
              {agent?.philosophy}
            </p>
            <div className="flex flex-wrap items-center gap-4 text-xs font-mono text-stone-500 pt-1">
              <span>Target Horizon: <strong className="text-stone-800 dark:text-stone-200">{agent?.horizonDays}</strong></span>
              <span>·</span>
              <span>Universe: <strong className="text-stone-800 dark:text-stone-200">NSE Nifty 500</strong></span>
              <span>·</span>
              <span>Faithfulness Score: <strong className="text-purple-600 dark:text-purple-400">{agent?.faithfulnessRatePct.toFixed(1)}%</strong></span>
            </div>
          </div>

          {/* Quick Balance Breakdown */}
          <div className="bg-stone-50 dark:bg-stone-800/60 rounded-xl p-4 border border-stone-200/80 dark:border-stone-700/60 flex items-center gap-6 text-xs font-mono">
            <div>
              <div className="text-stone-400 uppercase text-[10px]">TOTAL PORTFOLIO NAV</div>
              <div className="text-xl font-bold text-stone-900 dark:text-stone-100 mt-0.5">
                {formatPaiseToRupees(agent?.navPaise)}
              </div>
              <div className={`text-[11px] font-semibold mt-0.5 ${(agent?.returnPct || 0) >= 0 ? 'text-emerald-600' : 'text-rose-600'}`}>
                {formatPct(agent?.returnPct)} (Alpha: {formatPct(agent?.alphaVsBenchmarkPct)})
              </div>
            </div>
            <div className="h-10 w-px bg-stone-200 dark:bg-stone-700" />
            <div className="space-y-1">
              <div>
                <span className="text-stone-400">Available Cash: </span>
                <span className="font-semibold text-stone-800 dark:text-stone-200">{formatPaiseToRupees(cashPaise)}</span>
              </div>
              <div>
                <span className="text-stone-400">Invested Capital: </span>
                <span className="font-semibold text-stone-800 dark:text-stone-200">{formatPaiseToRupees(investedPaise)}</span>
              </div>
              <div>
                <span className="text-stone-400">Open Positions: </span>
                <span className="font-semibold text-stone-800 dark:text-stone-200">{positions.filter(p => p.status === 'OPEN').length} stocks</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Mandatory Small Sample Notice */}
      <SmallSampleNotice closedTradesCount={agent?.closedTrades || 0} threshold={30} />

      {/* Navigation Tabs */}
      <div className="flex border-b border-stone-200 dark:border-stone-800 space-x-6 text-sm font-medium">
        {[
          { key: 'positions', label: 'Positions & Forensics', count: positions.length, icon: Briefcase },
          { key: 'orders', label: 'Order Execution Log', count: orders.length, icon: ListOrdered },
          { key: 'decisions', label: 'LLM Faithfulness & Rationale', count: decisions.length, icon: Brain },
          { key: 'heuristics', label: 'Learned Heuristics (Memory)', count: heuristics.length, icon: Layers },
        ].map(({ key, label, count, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setActiveTab(key as typeof activeTab)}
            className={`pb-3 flex items-center gap-2 border-b-2 font-mono text-xs transition-colors cursor-pointer ${
              activeTab === key
                ? 'border-amber-500 text-amber-600 dark:text-amber-400 font-semibold'
                : 'border-transparent text-stone-500 hover:text-stone-800 dark:hover:text-stone-200'
            }`}
          >
            <Icon className="w-4 h-4" />
            <span>{label}</span>
            <span className="px-1.5 py-0.5 rounded-full text-[10px] bg-stone-100 dark:bg-stone-800 text-stone-600 dark:text-stone-400">
              {count}
            </span>
          </button>
        ))}
      </div>

      {/* TAB 1: POSITIONS */}
      {activeTab === 'positions' && (
        <div className="space-y-4">
          <PositionTable positions={positions} title="Position Ledger (Integer Paise Accounting)" />
        </div>
      )}

      {/* TAB 2: ORDERS */}
      {activeTab === 'orders' && (
        <div className="bg-white dark:bg-stone-900 rounded-xl border border-stone-200 dark:border-stone-800 shadow-sm overflow-hidden">
          <div className="p-4 border-b border-stone-200 dark:border-stone-800">
            <h3 className="text-base font-semibold text-stone-900 dark:text-stone-100">
              Broker Order Matching & Audit Log
            </h3>
            <p className="text-xs text-stone-500">
              Orders evaluated against daily OHLCV bounds. Unfilled orders expire daily at 15:30 IST.
            </p>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-stone-700 dark:text-stone-300">
              <thead className="bg-stone-50 dark:bg-stone-800/60 uppercase font-semibold text-[11px] text-stone-500 dark:text-stone-400 tracking-wider">
                <tr>
                  <th className="py-3 px-4">Order ID</th>
                  <th className="py-3 px-4">Symbol</th>
                  <th className="py-3 px-4">Side / Type</th>
                  <th className="py-3 px-4 text-right">Quantity</th>
                  <th className="py-3 px-4 text-right">Limit Price</th>
                  <th className="py-3 px-4 text-right">Filled Price</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4 text-right">Charges</th>
                  <th className="py-3 px-4">Submitted (IST)</th>
                  <th className="py-3 px-4">Notes / Rejection Reason</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-stone-100 dark:divide-stone-800">
                {orders.map((order) => (
                  <tr key={order.id} className="hover:bg-stone-50/70 dark:hover:bg-stone-800/40">
                    <td className="py-3 px-4 font-mono font-medium text-stone-400">#{order.id}</td>
                    <td className="py-3 px-4 font-mono font-semibold text-stone-900 dark:text-stone-100">{order.symbol}</td>
                    <td className="py-3 px-4 font-mono">
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${order.side === 'BUY' ? 'bg-emerald-100 text-emerald-800' : 'bg-rose-100 text-rose-800'}`}>
                        {order.side}
                      </span>{' '}
                      <span className="text-stone-400 text-[11px]">{order.orderType}</span>
                    </td>
                    <td className="py-3 px-4 text-right font-mono">{order.quantity}</td>
                    <td className="py-3 px-4 text-right font-mono">{formatPaiseToRupees(order.limitPricePaise)}</td>
                    <td className="py-3 px-4 text-right font-mono">
                      {order.filledPricePaise ? formatPaiseToRupees(order.filledPricePaise) : '-'}
                    </td>
                    <td className="py-3 px-4">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                        order.status === 'FILLED' ? 'bg-emerald-100 text-emerald-800' :
                        order.status === 'EXPIRED' ? 'bg-amber-100 text-amber-800' :
                        order.status === 'REJECTED' ? 'bg-rose-100 text-rose-800' : 'bg-stone-100 text-stone-700'
                      }`}>
                        {order.status}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right font-mono text-stone-500">
                      {formatPaiseToRupees(order.statutoryChargesPaise)}
                    </td>
                    <td className="py-3 px-4 font-mono text-[11px] text-stone-500">
                      {formatISTDateTime(order.submittedAt)}
                    </td>
                    <td className="py-3 px-4 text-stone-500 text-[11px] max-w-xs truncate">
                      {order.rejectionReason || 'Filled cleanly with standard statutory charges.'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 3: DECISIONS & FAITHFULNESS */}
      {activeTab === 'decisions' && (
        <div className="space-y-4">
          <div className="bg-white dark:bg-stone-900 rounded-xl border border-stone-200 dark:border-stone-800 p-4 shadow-sm">
            <h3 className="text-base font-semibold text-stone-900 dark:text-stone-100 mb-1">
              LLM Decision Faithfulness & Metric Citation Verification
            </h3>
            <p className="text-xs text-stone-500">
              Each LLM recommendation is verified against the underlying market <code>FeatureSnapshot</code>. Hallucinations or out-of-tolerance metric claims penalize the faithfulness score.
            </p>
          </div>

          {decisions.map((dec) => (
            <div
              key={dec.id}
              className="bg-white dark:bg-stone-900 rounded-xl border border-stone-200 dark:border-stone-800 p-5 shadow-xs space-y-4"
            >
              <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2 border-b border-stone-100 dark:border-stone-800 pb-3">
                <div className="flex items-center gap-3">
                  <span className={`px-2.5 py-1 rounded text-xs font-bold font-mono ${
                    dec.action === 'BUY' ? 'bg-emerald-100 text-emerald-800' :
                    dec.action === 'HOLD' ? 'bg-stone-100 text-stone-800' : 'bg-rose-100 text-rose-800'
                  }`}>
                    {dec.action} {dec.symbol}
                  </span>
                  <span className="text-xs font-mono text-stone-400">
                    Decision Date: {dec.decisionDate}
                  </span>
                </div>

                <div className="flex items-center gap-3 text-xs font-mono">
                  <div className="flex items-center gap-1.5 px-2 py-1 rounded bg-purple-50 dark:bg-purple-950/40 text-purple-700 dark:text-purple-300 border border-purple-200 dark:border-purple-800">
                    <ShieldCheck className="w-3.5 h-3.5" />
                    <span>Faithfulness: {(dec.faithfulnessScore * 100).toFixed(0)}%</span>
                  </div>
                  <div className="text-stone-500">
                    Rank: #{dec.candidateRank} ({dec.stageReached})
                  </div>
                </div>
              </div>

              {/* Rationale */}
              <div className="text-xs text-stone-700 dark:text-stone-300 leading-relaxed bg-stone-50 dark:bg-stone-800/40 p-3 rounded-lg">
                <span className="font-semibold text-stone-900 dark:text-stone-100">LLM Stated Rationale: </span>
                {dec.rationale}
              </div>

              {/* Cited Metrics Verification Table */}
              <div>
                <h4 className="text-xs font-semibold uppercase text-stone-400 tracking-wider mb-2 font-mono">
                  Cited Financial Metrics vs Ground-Truth Snapshot
                </h4>
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-2">
                  {dec.citedMetrics.map((cm, i) => (
                    <div
                      key={i}
                      className="p-2.5 rounded-lg border border-stone-200 dark:border-stone-800 bg-white dark:bg-stone-900/60 text-xs font-mono space-y-1"
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-stone-500 truncate" title={cm.name}>{cm.name}</span>
                        {cm.isFaithful ? (
                          <span title="Accurate cite within tolerance"><CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" /></span>
                        ) : (
                          <span title="Out of tolerance metric citation"><XCircle className="w-3.5 h-3.5 text-rose-500" /></span>
                        )}
                      </div>
                      <div className="flex justify-between items-baseline pt-1">
                        <span className="text-stone-400 text-[10px]">LLM: <strong className="text-stone-800 dark:text-stone-200">{cm.citedValue}</strong></span>
                        <span className="text-stone-400 text-[10px]">Truth: <strong className="text-stone-800 dark:text-stone-200">{cm.actualSnapshotValue}</strong></span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* TAB 4: HEURISTIC MEMORY */}
      {activeTab === 'heuristics' && (
        <div className="space-y-4">
          <div className="bg-white dark:bg-stone-900 rounded-xl border border-stone-200 dark:border-stone-800 p-4 shadow-sm">
            <h3 className="text-base font-semibold text-stone-900 dark:text-stone-100 mb-1">
              Agent Causal Forensics & Heuristic Memory Bank
            </h3>
            <p className="text-xs text-stone-500">
              Heuristics generated through automated post-mortem reflection on closed trades. Triggers are machine-checkable against future <code>FeatureSnapshot</code> instances.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {heuristics.map((h) => (
              <div
                key={h.id}
                className="bg-white dark:bg-stone-900 rounded-xl border border-stone-200 dark:border-stone-800 p-4 shadow-xs space-y-3"
              >
                <div className="flex justify-between items-start">
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold font-mono uppercase ${
                    h.kind === 'AVOID' ? 'bg-rose-100 text-rose-800 dark:bg-rose-950/60 dark:text-rose-300' : 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300'
                  }`}>
                    RULE: {h.kind}
                  </span>

                  <span className="px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-stone-100 dark:bg-stone-800 text-stone-700 dark:text-stone-300">
                    {h.status}
                  </span>
                </div>

                <p className="text-xs font-medium text-stone-800 dark:text-stone-200 leading-relaxed">
                  {h.ruleDescription}
                </p>

                <div className="bg-stone-50 dark:bg-stone-800/60 p-2.5 rounded-lg border border-stone-200/60 dark:border-stone-700/60 font-mono text-[11px] text-amber-700 dark:text-amber-300">
                  <div className="text-[9px] uppercase text-stone-400 mb-0.5">Machine Trigger Predicate:</div>
                  <code>{h.triggerPredicate}</code>
                </div>

                <div className="flex justify-between items-center text-xs font-mono text-stone-400 pt-1 border-t border-stone-100 dark:border-stone-800">
                  <span>Confidence: <strong className="text-stone-700 dark:text-stone-300">{(h.confidenceScore * 100).toFixed(0)}%</strong></span>
                  <span>Tested: <strong className="text-stone-700 dark:text-stone-300">{h.timesApplied}x ({h.successRatePct.toFixed(0)}% win)</strong></span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
