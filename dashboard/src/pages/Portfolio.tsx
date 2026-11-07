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
      <div className="max-w-7xl mx-auto px-4 py-16 flex justify-center items-center">
        <div className="flex items-center gap-3 text-[#7C8698] font-mono text-sm">
          <div className="w-4 h-4 border-2 border-[#8A7441] border-t-transparent rounded-full animate-spin" />
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
          className="inline-flex items-center gap-1.5 text-xs font-mono text-[#475060] hover:text-[#151B26] transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to strategy leaderboard</span>
        </Link>

        {/* Strategy Switcher */}
        <div className="flex items-center gap-2 text-xs font-mono">
          <span className="text-[#7C8698] hidden sm:inline">Active strategy:</span>
          <select
            value={currentAgentId}
            onChange={(e) => navigate(`/portfolio/${e.target.value}`)}
            className="bg-white border border-[#DCD7CC] text-[#151B26] rounded-[3px] px-3 py-1 font-mono text-xs cursor-pointer"
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
      <div className="ledger-panel p-6 bg-white space-y-4">
        <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-6">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-serif font-bold text-[#151B26]">
                {agent?.name || currentAgentId}
              </h1>
              <span
                className={`px-2 py-0.5 rounded-[2px] text-[10px] font-mono ${
                  config.badge === 'RULES'
                    ? 'bg-[#F6F4EF] text-[#475060] border border-[#DCD7CC]'
                    : 'bg-[#EDF2F9] text-[#2A4B7C] border border-[#B9C9E1]'
                }`}
              >
                {config.badge === 'RULES' ? 'Rules control' : 'LLM persona'}
              </span>
            </div>

            <p className="text-xs text-[#475060] max-w-2xl leading-relaxed">
              {agent?.philosophy}
            </p>

            <div className="flex flex-wrap items-center gap-4 text-xs font-mono text-[#7C8698] pt-1">
              <span>Family: <strong className="text-[#151B26]">{config.family}</strong></span>
              <span>·</span>
              <span>Universe: <strong className="text-[#151B26]">NSE Nifty 500</strong></span>
              <span>·</span>
              <span>Metric faithfulness: <strong className="text-[#2A4B7C]">{agent?.faithfulnessRatePct.toFixed(1)}%</strong></span>
            </div>
          </div>

          {/* Capital Matrix Inset */}
          <div className="p-4 rounded-[3px] border border-[#DCD7CC] bg-[#F6F4EF] flex items-center gap-6 font-mono text-xs">
            <div>
              <div className="text-[10px] text-[#7C8698]">Portfolio NAV</div>
              <div className="text-xl font-bold text-[#151B26] mt-0.5">
                {formatPaiseToRupees(agent?.navPaise)}
              </div>
              <div className={`text-[11px] font-medium mt-0.5 ${(agent?.returnPct || 0) >= 0 ? 'text-[#1E6548]' : 'text-[#933835]'}`}>
                {formatPct(agent?.returnPct)} (Alpha: +{formatPct(agent?.alphaVsBenchmarkPct)})
              </div>
            </div>

            <div className="h-10 w-px bg-[#DCD7CC]" />

            <div className="space-y-1 text-[11px]">
              <div>
                <span className="text-[#7C8698]">Available cash: </span>
                <span className="font-semibold text-[#151B26]">{formatPaiseToRupees(cashPaise)}</span>
              </div>
              <div>
                <span className="text-[#7C8698]">Invested equity: </span>
                <span className="font-semibold text-[#151B26]">{formatPaiseToRupees(investedPaise)}</span>
              </div>
              <div>
                <span className="text-[#7C8698]">Open positions: </span>
                <span className="font-semibold text-[#151B26]">{activePositions.length} stocks</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Small Sample Warning */}
      <SmallSampleNotice closedTradesCount={agent?.closedTrades || 0} threshold={30} />

      {/* Segmented Navigation Tabs */}
      <div className="flex border-b border-[#DCD7CC] space-x-6 text-xs font-mono font-medium">
        {[
          { key: 'active', label: 'Active positions', count: activePositions.length, icon: Briefcase },
          { key: 'past', label: 'Past trades ledger', count: closedPositions.length, icon: History },
          { key: 'orders', label: 'Broker orders', count: orders.length, icon: ListOrdered },
          { key: 'decisions', label: 'Decisions audit', count: decisions.length, icon: Brain },
          { key: 'heuristics', label: 'Heuristic memory', count: heuristics.length, icon: Layers },
        ].map(({ key, label, count, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setActiveTab(key as typeof activeTab)}
            className={`pb-3 flex items-center gap-2 border-b-2 transition-colors cursor-pointer ${
              activeTab === key
                ? 'border-[#8A7441] text-[#8A7441] font-semibold'
                : 'border-transparent text-[#475060] hover:text-[#151B26]'
            }`}
          >
            <Icon className="w-3.5 h-3.5" />
            <span>{label}</span>
            <span className="px-1.5 py-0.2 rounded-[2px] text-[10px] bg-[#F6F4EF] text-[#475060] border border-[#DCD7CC]">
              {count}
            </span>
          </button>
        ))}
      </div>

      {/* TAB CONTENT */}
      {activeTab === 'active' && (
        <PositionTable
          positions={activePositions}
          title="Active positions (Current holdings)"
          defaultStatus="OPEN"
        />
      )}

      {activeTab === 'past' && (
        <PositionTable
          positions={closedPositions}
          title="Historical trade log & forensics ledger"
          defaultStatus="CLOSED"
        />
      )}

      {activeTab === 'orders' && (
        <div className="ledger-panel overflow-hidden">
          <div className="p-4 border-b border-[#E7E3D9] bg-white">
            <h3 className="text-base font-serif font-bold text-[#151B26]">
              Broker execution & audit log
            </h3>
            <p className="text-xs text-[#7C8698]">
              Limit orders matched against daily OHLCV bands. Unfilled orders expire daily at 15:30 IST.
            </p>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono text-[#151B26]">
              <thead className="bg-[#F6F4EF] text-[11px] text-[#475060] border-b border-[#DCD7CC]">
                <tr>
                  <th className="py-2.5 px-4 font-medium">Order ID</th>
                  <th className="py-2.5 px-4 font-medium">Symbol</th>
                  <th className="py-2.5 px-4 font-medium">Side / Type</th>
                  <th className="py-2.5 px-4 text-right font-medium">Quantity</th>
                  <th className="py-2.5 px-4 text-right font-medium">Limit price</th>
                  <th className="py-2.5 px-4 text-right font-medium">Filled price</th>
                  <th className="py-2.5 px-4 font-medium">Status</th>
                  <th className="py-2.5 px-4 text-right font-medium">Charges</th>
                  <th className="py-2.5 px-4 font-medium">Submitted (IST)</th>
                  <th className="py-2.5 px-4 font-medium">Rejection reason / Notes</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E7E3D9]">
                {orders.map((ord) => (
                  <tr key={ord.id} className="hover:bg-[#F6F4EF] transition-colors">
                    <td className="py-3 px-4 text-[#7C8698]">#{ord.id}</td>
                    <td className="py-3 px-4 font-semibold">{ord.symbol}</td>
                    <td className="py-3 px-4">
                      <span className={`px-1.5 py-0.2 rounded-[2px] text-[10px] font-medium ${ord.side === 'BUY' ? 'bg-[#EBF5F0] text-[#1E6548] border border-[#A3D4BE]' : 'bg-[#FBF0F0] text-[#933835] border border-[#E5ACAA]'}`}>
                        {ord.side}
                      </span>{' '}
                      <span className="text-[#7C8698] text-[10px]">{ord.orderType}</span>
                    </td>
                    <td className="py-3 px-4 text-right font-medium">{ord.quantity}</td>
                    <td className="py-3 px-4 text-right">{formatPaiseToRupees(ord.limitPricePaise)}</td>
                    <td className="py-3 px-4 text-right font-medium">
                      {ord.filledPricePaise ? formatPaiseToRupees(ord.filledPricePaise) : '-'}
                    </td>
                    <td className="py-3 px-4">
                      <span className={`px-2 py-0.5 rounded-[2px] text-[10px] font-medium border ${
                        ord.status === 'FILLED' ? 'bg-[#EBF5F0] text-[#1E6548] border-[#A3D4BE]' :
                        ord.status === 'EXPIRED' ? 'bg-[#F3EFE6] text-[#8A7441] border-[#D6C7A1]' :
                        ord.status === 'REJECTED' ? 'bg-[#FBF0F0] text-[#933835] border-[#E5ACAA]' : 'bg-[#F6F4EF] text-[#475060] border-[#DCD7CC]'
                      }`}>
                        {ord.status}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right text-[#475060]">
                      {formatPaiseToRupees(ord.statutoryChargesPaise)}
                    </td>
                    <td className="py-3 px-4 text-[11px] text-[#475060]">
                      {formatISTDateTime(ord.submittedAt)}
                    </td>
                    <td className="py-3 px-4 text-[#475060] text-[11px] truncate max-w-xs font-sans">
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
          <div className="ledger-panel p-4">
            <h3 className="font-serif font-bold text-base text-[#151B26]">
              Decision faithfulness & verbatim rationale inspector
            </h3>
            <p className="text-xs text-[#7C8698]">
              Every metric citation is deterministically checked against the saved market snapshot.
            </p>
          </div>

          {decisions.map((dec) => (
            <div key={dec.id} className="ledger-panel p-5 space-y-3">
              <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2 border-b border-[#E7E3D9] pb-2">
                <div className="flex items-center gap-2.5">
                  <span className={`px-2 py-0.5 rounded-[2px] text-xs font-mono font-medium border ${
                    dec.action === 'BUY' ? 'bg-[#EBF5F0] text-[#1E6548] border-[#A3D4BE]' : 'bg-[#F6F4EF] text-[#475060] border-[#DCD7CC]'
                  }`}>
                    {dec.action} {dec.symbol}
                  </span>
                  <span className="text-xs font-mono text-[#7C8698]">
                    Date: {dec.decisionDate}
                  </span>
                </div>

                <div className="text-xs font-mono text-[#2A4B7C] bg-[#EDF2F9] px-2 py-0.5 rounded-[2px] border border-[#B9C9E1]">
                  Faithfulness: {(dec.faithfulnessScore * 100).toFixed(0)}%
                </div>
              </div>

              <div className="p-3 rounded-[2px] bg-[#F6F4EF] text-xs text-[#151B26] leading-relaxed italic border border-[#E7E3D9]">
                "{dec.rationale}"
              </div>

              {/* Cited Metrics Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 pt-1 font-mono text-xs">
                {dec.citedMetrics.map((cm, i) => (
                  <div key={i} className="p-2 rounded-[2px] border border-[#DCD7CC] bg-white flex justify-between items-center">
                    <div>
                      <span className="text-[10px] text-[#475060] block">{cm.name}</span>
                      <span className="font-medium text-[#151B26]">
                        {cm.citedValue} <span className="text-[#7C8698] font-normal">(Truth: {cm.actualSnapshotValue})</span>
                      </span>
                    </div>
                    <span className="text-[#1E6548] font-semibold text-xs">✓</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {activeTab === 'heuristics' && (
        <div className="space-y-4">
          <div className="ledger-panel p-4">
            <h3 className="font-serif font-bold text-base text-[#151B26]">
              Causal forensics & heuristic memory bank
            </h3>
            <p className="text-xs text-[#7C8698]">
              Machine-checkable rules extracted by the weekly reflection loop from closed trade post-mortems.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {heuristics.map((h) => (
              <div key={h.id} className="ledger-panel p-4 space-y-2.5">
                <div className="flex justify-between items-center text-xs font-mono">
                  <span className={`px-2 py-0.5 rounded-[2px] font-medium border ${
                    h.kind === 'AVOID' ? 'bg-[#FBF0F0] text-[#933835] border-[#E5ACAA]' : 'bg-[#EBF5F0] text-[#1E6548] border-[#A3D4BE]'
                  }`}>
                    {h.kind}
                  </span>
                  <span className="px-2 py-0.5 rounded-[2px] bg-[#F6F4EF] text-[#475060] font-medium border border-[#DCD7CC]">
                    {h.status}
                  </span>
                </div>

                <p className="text-xs font-medium text-[#151B26] leading-relaxed font-sans">
                  {h.ruleDescription}
                </p>

                <div className="flex justify-between items-center text-xs font-mono text-[#7C8698] pt-2 border-t border-[#E7E3D9]">
                  <span>Confidence: <strong className="text-[#151B26]">{(h.confidenceScore * 100).toFixed(0)}%</strong></span>
                  <span>Tested: <strong className="text-[#151B26]">{h.timesApplied}x ({h.successRatePct.toFixed(0)}% win)</strong></span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
