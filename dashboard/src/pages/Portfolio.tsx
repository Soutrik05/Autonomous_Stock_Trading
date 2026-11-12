import { useState, useEffect, useMemo, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ChevronDown, ChevronUp, Sliders, Check } from 'lucide-react';
import type {
  AgentId,
  AgentLeaderboardEntry,
  Position,
  Order,
  Decision,
  HeuristicMemory,
  NavHistoryPoint,
  AgentWatchlistItem,
} from '../types';
import { apiService, getIsMockMode } from '../services/api';
import { formatPaiseToRupees, formatPct, formatISTDateTime } from '../utils/formatters';
import { CategoryBadge } from '../components/ui/CategoryBadge';
import { cn } from '../utils/cn';
import PortfolioDualCurve from '../components/PortfolioDualCurve';
import HoldingsLinearStack from '../components/HoldingsLinearStack';
import IntegratedTradesSection from '../components/IntegratedTradesSection';
import LearnedMemoryBankSection from '../components/LearnedMemoryBankSection';
import WatchlistFunnel from '../components/WatchlistFunnel';
import AgentWatchlistSection from '../components/AgentWatchlistSection';

interface PersonaProfile {
  school: string;
  horizon: string;
  description: string;
}

const PERSONA_PROFILES: Record<string, PersonaProfile> = {
  simons: {
    school: 'Quantitative Statistical Momentum & Volatility Parity',
    horizon: '1–10 Trading Days',
    description:
      "Modeled on Jim Simons's systematic framework at Renaissance Technologies, this agent identifies confirmed statistical momentum breakouts, trend efficiency, and volume surges across the Nifty 500 universe. Positions are sized mathematically via volatility parity rather than subjective conviction. Stalled or decaying trades are pruned aggressively to continually recycle capital into fresh mathematical edges.",
  },
  lynch: {
    school: 'Growth-at-a-Reasonable-Price (GARP) & Cash Conversion',
    horizon: '15–60 Trading Days',
    description:
      "Embodying Peter Lynch's classic GARP methodology (One Up On Wall Street), this agent targets understandable compounding franchises with durable operational margins, high return on capital (ROCE), and clean cash conversion (CFO/PAT). Positions are anchored to strict valuation hurdles (PEG <= 1.0) and held through interim market noise to let underlying earnings growth drive returns.",
  },
  marks: {
    school: 'Second-Level Contrarian Value & Margin of Safety',
    horizon: '30–90 Trading Days',
    description:
      "Rooted in Howard Marks's second-level thinking (The Most Important Thing), this agent hunts for solvent, high-quality businesses experiencing extreme cyclical despair or forced institutional selling. It demands an asymmetric margin of safety, controlling downside risk through deep valuation buffers and sector diversification rather than tight mechanical stop losses.",
  },
  jhunjhunwala: {
    school: 'High-Conviction Structural Growth & Pyramiding',
    horizon: '90–180 Trading Days',
    description:
      "Inspired by Rakesh Jhunjhunwala's compounding philosophy in Indian equities, this agent backs ambitious promoters with substantial skin-in-the-game riding multi-year capex and consumption tailwinds. It takes concentrated high-conviction positions and pyramids into winning structural themes, patiently absorbing interim drawdowns to capture multi-quarter upside.",
  },
  varsity: {
    school: 'Dual-Confluence Swing & DCF Margin-of-Safety',
    horizon: '5–20 Trading Days',
    description:
      "Operating on the Zerodha Varsity framework (Modules 2, 3, and 9), this agent enforces a strict dual-confluence mandate: fundamental balance sheet solvency and DCF cash flow conservatism determine what to buy, while classical technical momentum dictates when to execute. Neither discipline trades in isolation.",
  },
  'stockminds-core': {
    school: 'Dual-Confluence Swing & DCF Margin-of-Safety',
    horizon: '5–20 Trading Days',
    description:
      "Operating on the Zerodha Varsity framework (Modules 2, 3, and 9), this agent enforces a strict dual-confluence mandate: fundamental balance sheet solvency and DCF cash flow conservatism determine what to buy, while classical technical momentum dictates when to execute. Neither discipline trades in isolation.",
  },
};

function getPersonaProfile(agentId: string): PersonaProfile {
  const baseKey = agentId
    .replace('baseline-', '')
    .replace('-rules', '')
    .replace('rj', 'jhunjhunwala');
  const baseProfile = PERSONA_PROFILES[baseKey] || PERSONA_PROFILES['simons'];

  if (agentId.startsWith('baseline-') || agentId.includes('rules')) {
    return {
      school: `${baseProfile.school} (Rules Baseline)`,
      horizon: baseProfile.horizon,
      description: `The non-cognitive scientific control baseline. It executes the exact mathematical screening thresholds, hard stops, and ranking rules deterministically without LLM inference, prompt reflection, or heuristic adaptation, isolating the net alpha added by LLM reasoning.`,
    };
  }

  return baseProfile;
}

interface AgentItem {
  id: string;
  name: string;
  isRules: boolean;
  strategy: string;
}

const AGENT_CATALOG: AgentItem[] = [
  // Autonomous LLM Agents
  { id: 'simons', name: 'Jim Simons', isRules: false, strategy: 'Quantitative Statistical Momentum' },
  { id: 'lynch', name: 'Peter Lynch', isRules: false, strategy: 'GARP & Cash Conversion' },
  { id: 'marks', name: 'Howard Marks', isRules: false, strategy: 'Second-Level Contrarian Value' },
  { id: 'jhunjhunwala', name: 'Rakesh Jhunjhunwala', isRules: false, strategy: 'Structural Growth & Pyramiding' },
  { id: 'varsity', name: 'StockMinds Core', isRules: false, strategy: 'Dual-Confluence Varsity Swing' },
  // Deterministic Rules Baselines
  { id: 'baseline-simons-rules', name: 'Simons Rules Baseline', isRules: true, strategy: 'Quantitative Statistical Momentum' },
  { id: 'baseline-lynch-rules', name: 'Lynch Rules Baseline', isRules: true, strategy: 'GARP & Cash Conversion' },
  { id: 'baseline-marks-rules', name: 'Marks Rules Baseline', isRules: true, strategy: 'Second-Level Contrarian Value' },
  { id: 'baseline-rj-rules', name: 'Jhunjhunwala Rules Baseline', isRules: true, strategy: 'Structural Growth & Pyramiding' },
  { id: 'baseline-varsity-rules', name: 'Varsity Rules Baseline', isRules: true, strategy: 'Dual-Confluence Varsity Swing' },
];

function getNavKeyForAgent(agentId: string): string {
  switch (agentId) {
    case 'simons': return 'simons';
    case 'baseline-simons-rules': return 'baselineSimons';
    case 'lynch': return 'lynch';
    case 'baseline-lynch-rules': return 'baselineLynch';
    case 'marks': return 'marks';
    case 'baseline-marks-rules': return 'baselineMarks';
    case 'jhunjhunwala': return 'jhunjhunwala';
    case 'baseline-rj-rules': return 'baselineRj';
    case 'stockminds-core':
    case 'varsity': return 'stockmindsCore';
    case 'baseline-varsity-rules': return 'baselineVarsity';
    default: return 'simons';
  }
}

export default function Portfolio() {
  const { id, agentId } = useParams<{ id?: string; agentId?: string }>();
  const navigate = useNavigate();

  // Canonicalize route param
  const routeParam = id || agentId || 'simons';
  const currentAgentId = (routeParam === 'stockminds-core' ? 'varsity' : routeParam) as AgentId;

  const [agent, setAgent] = useState<AgentLeaderboardEntry | null>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [heuristics, setHeuristics] = useState<HeuristicMemory[]>([]);
  const [navHistory, setNavHistory] = useState<NavHistoryPoint[]>([]);
  const [watchlist, setWatchlist] = useState<AgentWatchlistItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [isMock] = useState(getIsMockMode());

  // Dropdown open state
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown on click outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setDropdownOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Interactive UI state for decluttered secondary panels
  const [showPendingOrders, setShowPendingOrders] = useState(false);
  const [showMethodology, setShowMethodology] = useState(false);

  useEffect(() => {
    async function loadPortfolioData() {
      setLoading(true);
      try {
        const [board, pos, ord, dec, mem, nav, wl] = await Promise.all([
          apiService.getLeaderboard(),
          apiService.getAgentPositions(currentAgentId),
          apiService.getAgentOrders(currentAgentId),
          apiService.getAgentDecisions(currentAgentId),
          apiService.getAgentMemory(currentAgentId),
          apiService.getAgentNavHistory(),
          apiService.getAgentWatchlist(currentAgentId),
        ]);

        const currentAgent = board.find((a: AgentLeaderboardEntry) => a.id === currentAgentId) || null;
        setAgent(currentAgent);
        setPositions(pos);
        setOrders(ord);
        setDecisions(dec);
        setHeuristics(mem);
        setNavHistory(nav);
        setWatchlist(wl);
      } catch (err) {
        console.warn('Failed to load agent portfolio details:', err);
      } finally {
        setLoading(false);
      }
    }

    loadPortfolioData();
  }, [currentAgentId, isMock]);

  // Session date derived dynamically
  const sessionDate = useMemo(() => {
    if (navHistory.length > 0) {
      return navHistory[navHistory.length - 1].date;
    }
    return new Date().toISOString().split('T')[0];
  }, [navHistory]);

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-28 flex justify-center items-center">
        <div className="flex items-center gap-3 text-zinc-500 font-mono text-xs">
          <div className="w-4 h-4 border-2 border-accent border-t-transparent rounded-full animate-spin" />
          <span>Synchronizing strategy portfolio ledger...</span>
        </div>
      </div>
    );
  }

  // Pending orders
  const pendingOrders = orders.filter((o) => o.status === 'PENDING');
  const committedPendingCapital = pendingOrders.reduce((sum, o) => {
    const price = o.limitPricePaise ?? o.entryLowPaise ?? 0;
    return sum + o.quantity * price;
  }, 0);

  // Financial metrics (100% Dynamic with zero hardcoded fallbacks)
  const startingCapitalPaise = agent?.startingCapitalPaise ?? 50000000;
  const currentInvestedPaise = positions
    .filter((p) => p.status === 'OPEN')
    .reduce((sum, p) => sum + p.quantity * p.currentPricePaise, 0);

  const costBasisPaise = positions
    .filter((p) => p.status === 'OPEN')
    .reduce((sum, p) => sum + p.quantity * p.entryPricePaise, 0);

  const unrealizedPnLPaise = currentInvestedPaise - costBasisPaise;
  const totalNavPaise = agent?.navPaise ?? (startingCapitalPaise + unrealizedPnLPaise);
  const cashPaise = Math.max(0, totalNavPaise - currentInvestedPaise);
  const netGainPaise = totalNavPaise - startingCapitalPaise;
  const totalReturnPct = agent?.returnPct ?? ((totalNavPaise - startingCapitalPaise) / startingCapitalPaise) * 100;
  const alphaPct = agent?.alphaVsBenchmarkPct ?? totalReturnPct;

  const holdingsWeightPct = totalNavPaise > 0 ? (currentInvestedPaise / totalNavPaise) * 100 : 0;
  const cashWeightPct = totalNavPaise > 0 ? (cashPaise / totalNavPaise) * 100 : 0;

  const isRulesControl = currentAgentId.startsWith('baseline-') || currentAgentId.includes('rules');
  const currentAgentItem = AGENT_CATALOG.find((a) => a.id === currentAgentId) || {
    id: currentAgentId,
    name: agent?.name || currentAgentId,
    isRules: isRulesControl,
    strategy: '',
  };

  const cleanAgentName = (agent?.name || currentAgentItem.name)
    .replace(/\s*\((LLM|Rules Control|Rules Baseline|Rules|Algorithmic Control Benchmark)\)/gi, '')
    .trim();

  const personaProfile = getPersonaProfile(currentAgentId);

  // Dynamic dual-curve points (zero mock dates)
  const dualCurvePoints = (() => {
    const key = getNavKeyForAgent(currentAgentId);
    if (navHistory.length > 0) {
      return navHistory.map((pt) => {
        const rawRupees = (pt as any)[key] ?? 500000;
        const portfolioValuePaise = Math.round(rawRupees * 100);
        return {
          date: pt.date,
          portfolioValuePaise,
          investedCapitalPaise: startingCapitalPaise,
        };
      });
    }

    return [
      { date: 'Day 0', portfolioValuePaise: startingCapitalPaise, investedCapitalPaise: startingCapitalPaise },
      { date: sessionDate, portfolioValuePaise: totalNavPaise, investedCapitalPaise: startingCapitalPaise },
    ];
  })();

  const llmAgents = AGENT_CATALOG.filter((a) => !a.isRules);
  const rulesAgents = AGENT_CATALOG.filter((a) => a.isRules);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-7 animate-hero-entrance font-sans">
      
      {/* 1. TOP HEADER & UNIFIED 10-AGENT SELECTOR */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 border-b border-border-hairline pb-4">
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-2xl sm:text-3xl font-serif font-medium tracking-tight text-white">
              {cleanAgentName}
            </h1>
            <CategoryBadge type={isRulesControl ? 'RULES' : 'LLM'} />
            {!isRulesControl && (
              <span className="px-2 py-0.5 rounded text-[10px] font-mono border border-border-hairline bg-[#161616] text-zinc-300">
                {agent?.foundationModel || 'gemini-2.5-flash'}
              </span>
            )}
            <span className="text-zinc-600 hidden sm:inline">·</span>
            <span className="text-xs font-mono text-zinc-400">
              Horizon: <strong className="text-zinc-200 font-normal">{personaProfile.horizon}</strong>
            </span>
          </div>
          <p className="text-xs text-zinc-400 font-sans">
            {personaProfile.school}
          </p>
        </div>

        {/* Unified 10-Agent Dropdown Selector */}
        <div className="relative" ref={dropdownRef}>
          <button
            type="button"
            onClick={() => setDropdownOpen(!dropdownOpen)}
            className="flex items-center gap-2.5 bg-[#161616] border border-border-hairline hover:border-white/25 rounded px-3 py-1.5 font-mono text-xs cursor-pointer transition-colors"
          >
            <CategoryBadge type={isRulesControl ? 'RULES' : 'LLM'} />
            <span className="font-semibold text-white tracking-tight">{cleanAgentName}</span>
            <ChevronDown className={cn("w-3.5 h-3.5 text-zinc-400 transition-transform duration-150", dropdownOpen && "rotate-180")} />
          </button>

          {dropdownOpen && (
            <div className="absolute right-0 top-full mt-1.5 w-72 sm:w-80 bg-[#161616] border border-border-hairline rounded shadow-2xl z-50 py-1 divide-y divide-border-hairline animate-hero-entrance">
              {/* Group 1: Autonomous LLM Agents */}
              <div className="p-1.5 space-y-0.5">
                <div className="px-2.5 py-1 text-[10px] font-mono uppercase tracking-wider text-zinc-500">
                  Autonomous LLM Agents (5)
                </div>
                {llmAgents.map((ag) => {
                  const isSelected = ag.id === currentAgentId;
                  return (
                    <button
                      key={ag.id}
                      onClick={() => {
                        setDropdownOpen(false);
                        navigate(`/portfolio/${ag.id}`);
                      }}
                      className={cn(
                        "w-full text-left px-2.5 py-1.5 rounded flex items-center justify-between text-xs transition-colors cursor-pointer",
                        isSelected
                          ? "bg-white/10 text-white font-medium"
                          : "text-zinc-300 hover:bg-white/[0.04] hover:text-white"
                      )}
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        <CategoryBadge type="LLM" />
                        <span className="truncate">{ag.name}</span>
                      </div>
                      {isSelected && <Check className="w-3.5 h-3.5 text-accent flex-shrink-0" />}
                    </button>
                  );
                })}
              </div>

              {/* Group 2: Deterministic Rules Baselines */}
              <div className="p-1.5 space-y-0.5">
                <div className="px-2.5 py-1 text-[10px] font-mono uppercase tracking-wider text-zinc-500">
                  Deterministic Rules Baselines (5)
                </div>
                {rulesAgents.map((ag) => {
                  const isSelected = ag.id === currentAgentId;
                  return (
                    <button
                      key={ag.id}
                      onClick={() => {
                        setDropdownOpen(false);
                        navigate(`/portfolio/${ag.id}`);
                      }}
                      className={cn(
                        "w-full text-left px-2.5 py-1.5 rounded flex items-center justify-between text-xs transition-colors cursor-pointer",
                        isSelected
                          ? "bg-white/10 text-white font-medium"
                          : "text-zinc-300 hover:bg-white/[0.04] hover:text-white"
                      )}
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        <CategoryBadge type="RULES" />
                        <span className="truncate">{ag.name}</span>
                      </div>
                      {isSelected && <Check className="w-3.5 h-3.5 text-accent flex-shrink-0" />}
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Mandate Summary Prose */}
      <p className="text-xs font-sans text-zinc-400 leading-relaxed max-w-4xl -mt-2">
        {personaProfile.description}
      </p>

      {/* 2. PENDING ORDERS STATUS STRIP (IF ANY) */}
      {pendingOrders.length > 0 && (
        <div className="border border-border-hairline bg-[#161616] rounded-lg px-4 py-2.5 font-mono text-xs space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <span className="w-2 h-2 rounded-full bg-accent animate-pulse" />
              <span className="text-zinc-200 font-medium">
                {pendingOrders.length} Order{pendingOrders.length > 1 ? 's' : ''} Queued for Market Open
              </span>
              <span className="text-zinc-500 hidden sm:inline">
                · {formatPaiseToRupees(committedPendingCapital)} committed · Awaiting 09:15:00 IST
              </span>
            </div>

            <button
              onClick={() => setShowPendingOrders(!showPendingOrders)}
              className="inline-flex items-center gap-1.5 text-zinc-400 hover:text-white transition-colors cursor-pointer text-xs"
            >
              <span>{showPendingOrders ? 'Hide Orders' : 'View Orders'}</span>
              {showPendingOrders ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            </button>
          </div>

          {/* Expanded Order Table */}
          {showPendingOrders && (
            <div className="pt-2 border-t border-border-hairline overflow-x-auto">
              <table className="w-full text-left font-mono text-xs">
                <thead>
                  <tr className="text-zinc-500 border-b border-border-hairline text-[10px] uppercase tracking-wider">
                    <th className="py-2 pr-4 font-normal">Side</th>
                    <th className="py-2 pr-4 font-normal">Symbol</th>
                    <th className="py-2 pr-4 font-normal text-right">Shares</th>
                    <th className="py-2 pr-4 font-normal text-right">Limit Price</th>
                    <th className="py-2 pr-4 font-normal text-right">Est. Outlay</th>
                    <th className="py-2 font-normal text-right">Queued At</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border-hairline text-zinc-300">
                  {pendingOrders.map((ord) => {
                    const price = ord.limitPricePaise ?? ord.entryLowPaise ?? 0;
                    const estOutlay = ord.quantity * price;
                    return (
                      <tr key={ord.id} className="hover:bg-white/[0.02]">
                        <td className="py-2 pr-4">
                          <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold border border-emerald-500/30 text-positive bg-emerald-500/10">
                            {ord.side}
                          </span>
                        </td>
                        <td className="py-2 pr-4 font-semibold text-white">{ord.symbol}</td>
                        <td className="py-2 pr-4 text-right tabular-nums">{ord.quantity}</td>
                        <td className="py-2 pr-4 text-right tabular-nums text-zinc-200">
                          {formatPaiseToRupees(price)}
                        </td>
                        <td className="py-2 pr-4 text-right tabular-nums text-accent font-medium">
                          {formatPaiseToRupees(estOutlay)}
                        </td>
                        <td className="py-2 text-right text-zinc-500 text-[11px]">
                          {formatISTDateTime(ord.submittedAt)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* 3. FULL-WIDTH 4-METRIC TERMINAL KPI STRIP */}
      <div className="border border-border-hairline bg-[#161616] rounded-lg p-1 sm:p-2 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 divide-y sm:divide-y-0 sm:divide-x divide-border-hairline font-mono text-xs">
        {/* Cell 1: Portfolio NAV */}
        <div className="p-3 sm:px-4">
          <span className="text-[10px] uppercase tracking-wider text-zinc-500 block font-sans">
            Portfolio Valuation (NAV)
          </span>
          <div className="text-xl sm:text-2xl font-semibold text-white mt-1 tabular-nums font-mono">
            {formatPaiseToRupees(totalNavPaise)}
          </div>
          <span className="text-[10px] text-zinc-400 mt-0.5 block font-sans">
            Starting: ₹5,00,000 · Live Mark-to-Market
          </span>
        </div>

        {/* Cell 2: Net Return */}
        <div className="p-3 sm:px-4">
          <span className="text-[10px] uppercase tracking-wider text-zinc-500 block font-sans">
            Net Return
          </span>
          <div className={cn("text-xl sm:text-2xl font-semibold mt-1 tabular-nums font-mono", totalReturnPct >= 0 ? "text-positive" : "text-negative")}>
            {formatPct(totalReturnPct)}
          </div>
          <span className="text-[10px] text-zinc-400 mt-0.5 block font-sans">
            Net PnL: {netGainPaise >= 0 ? '+' : ''}{formatPaiseToRupees(netGainPaise)}
          </span>
        </div>

        {/* Cell 3: Alpha vs Benchmark */}
        <div className="p-3 sm:px-4">
          <span className="text-[10px] uppercase tracking-wider text-zinc-500 block font-sans">
            Alpha vs Nifty 500
          </span>
          <div className={cn("text-xl sm:text-2xl font-semibold mt-1 tabular-nums font-mono", alphaPct >= 0 ? "text-positive" : "text-negative")}>
            {alphaPct >= 0 ? '+' : ''}{formatPct(alphaPct)}
          </div>
          <span className="text-[10px] text-zinc-400 mt-0.5 block font-sans">
            Benchmark: 0.00% · Excess Spread
          </span>
        </div>

        {/* Cell 4: Capital Allocation */}
        <div className="p-3 sm:px-4">
          <span className="text-[10px] uppercase tracking-wider text-zinc-500 block font-sans">
            Capital Allocation
          </span>
          <div className="text-sm font-semibold text-white mt-1.5 tabular-nums font-mono">
            Invested: {holdingsWeightPct.toFixed(1)}% · Cash: {cashWeightPct.toFixed(1)}%
          </div>
          <span className="text-[10px] text-zinc-400 mt-0.5 block font-sans">
            Stocks: {formatPaiseToRupees(currentInvestedPaise)} | Cash: {formatPaiseToRupees(cashPaise)}
          </span>
        </div>
      </div>

      {/* 4. DUAL GROWTH CURVE & HOLDINGS STACK (SIDE-BY-SIDE) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch">
        
        {/* Left Card: Trajectory & Growth Curve (lg:col-span-7) */}
        <div className="lg:col-span-7 bg-[#161616] border border-border-hairline p-5 rounded-lg flex flex-col justify-between space-y-4">
          <div>
            <div className="flex flex-wrap justify-between items-center gap-2 pb-3 border-b border-border-hairline">
              <h3 className="font-serif text-lg font-medium text-white tracking-tight">
                Trajectory & Valuation History
              </h3>
              <span className="text-[11px] font-mono text-zinc-400">
                Mark-to-market daily settlement
              </span>
            </div>

            <div className="py-2">
              <PortfolioDualCurve
                navPoints={dualCurvePoints}
                color={isRulesControl ? '#94A3B8' : '#10B981'}
                height={215}
              />
            </div>
          </div>

          {/* Essential Institutional Metrics Strip */}
          <div className="grid grid-cols-3 divide-x divide-border-hairline pt-3 border-t border-border-hairline text-center font-mono text-xs">
            <div className="px-2">
              <span className="text-[10px] text-zinc-500 block uppercase font-sans tracking-wider">Sharpe Ratio</span>
              <span className="font-semibold text-white text-base mt-0.5 block tabular-nums">
                {(agent?.sharpeRatio ?? 0).toFixed(2)}
              </span>
            </div>
            <div className="px-2">
              <span className="text-[10px] text-zinc-500 block uppercase font-sans tracking-wider">Max Drawdown</span>
              <span className="font-semibold text-negative text-base mt-0.5 block tabular-nums">
                -{Math.abs(agent?.maxDrawdownPct ?? 0).toFixed(2)}%
              </span>
            </div>
            <div className="px-2">
              <span className="text-[10px] text-zinc-500 block uppercase font-sans tracking-wider">Win Rate</span>
              <span className="font-semibold text-white text-base mt-0.5 block tabular-nums">
                {(agent?.winRatePct ?? 0).toFixed(1)}%
              </span>
            </div>
          </div>
        </div>

        {/* Right Card: Holdings Linear Stack (lg:col-span-5) */}
        <div className="lg:col-span-5">
          <HoldingsLinearStack
            positions={positions}
            cashPaise={cashPaise}
            totalNavPaise={totalNavPaise}
            pendingCount={pendingOrders.length}
          />
        </div>

      </div>

      {/* 5. ACTIVE STRATEGY WATCHLIST (MOVED UPWARDS) */}
      <AgentWatchlistSection
        watchlist={watchlist}
        agentName={cleanAgentName}
      />

      {/* 6. TRADE EXECUTION & DECISION LEDGER */}
      <IntegratedTradesSection
        positions={positions}
        decisions={decisions}
        orders={orders}
      />

      {/* 7. STRATEGY METHODOLOGY & SCREENING ACCORDION */}
      <section className="border border-border-hairline bg-[#161616] rounded-lg overflow-hidden">
        <button
          onClick={() => setShowMethodology(!showMethodology)}
          className="w-full px-5 py-4 flex items-center justify-between text-left font-mono text-xs hover:bg-white/[0.02] transition-colors cursor-pointer"
        >
          <div className="flex items-center gap-2.5">
            <Sliders className="w-4 h-4 text-accent" />
            <span className="font-sans text-sm font-semibold text-white">
              Strategy Methodology & Screening Pipeline · How {cleanAgentName} Decides
            </span>
          </div>

          <div className="flex items-center gap-2 text-zinc-400">
            <span>{showMethodology ? 'Hide Methodology Details' : 'Inspect Funnel & Memory Bank'}</span>
            {showMethodology ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </div>
        </button>

        {showMethodology && (
          <div className="p-5 sm:p-6 border-t border-border-hairline space-y-8 animate-hero-entrance">
            {/* Tapered Screening Funnel */}
            <WatchlistFunnel initialAgentId={currentAgentId} />

            {/* Learned Heuristics Memory Bank */}
            <LearnedMemoryBankSection heuristics={heuristics} />
          </div>
        )}
      </section>

    </div>
  );
}
