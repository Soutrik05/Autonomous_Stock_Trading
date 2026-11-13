import { useState, useEffect, useMemo, useRef } from 'react';
import { useParams, useNavigate, useSearchParams, Link } from 'react-router-dom';
import { ChevronDown, ChevronUp, Check, ExternalLink } from 'lucide-react';
import type {
  AgentId,
  AgentLeaderboardEntry,
  Position,
  Order,
  HeuristicMemory,
  NavHistoryPoint,
  AgentWatchlistItem,
} from '../types';
import { apiService, getIsMockMode, TELEMETRY_POLL_INTERVAL_MS } from '../services/api';
import { formatPaiseToRupees, formatPct, formatISTDateTime } from '../utils/formatters';
import { CategoryBadge } from '../components/ui/CategoryBadge';
import { WarmupMetric } from '../components/ui/WarmupMetric';
import { cn } from '../utils/cn';
import PortfolioDualCurve from '../components/PortfolioDualCurve';
import HoldingsLinearStack from '../components/HoldingsLinearStack';
import ClosedTradesList from '../components/ClosedTradesList';
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
    school: 'Quantitative Statistical Momentum',
    horizon: '1–10 Trading Days',
    description:
      "Modeled on Jim Simons's systematic framework at Renaissance Technologies, this agent identifies confirmed statistical momentum breakouts, trend efficiency, and volume surges across the Nifty 500 universe. Positions are sized mathematically via volatility parity rather than subjective conviction. Stalled or decaying trades are pruned aggressively to continually recycle capital into fresh mathematical edges.",
  },
  lynch: {
    school: 'Growth-at-a-Reasonable-Price (GARP) & Cash Conversion',
    horizon: '30–90 Trading Days',
    description:
      "Embodying Peter Lynch's classic GARP methodology (One Up On Wall Street), this agent targets understandable compounding franchises with durable operational margins, high return on capital (ROCE), and clean cash conversion (CFO/PAT). Positions are anchored to strict valuation hurdles (PEG <= 1.0) and held through interim market noise to let underlying earnings growth drive returns.",
  },
  marks: {
    school: 'Second-Level Contrarian Value & Margin of Safety',
    horizon: '60–120 Trading Days',
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
    school: 'Textbook Dual-Confluence Investing',
    horizon: '20–75 Trading Days',
    description:
      "Operating on the Zerodha Varsity framework, this agent enforces a strict dual-confluence mandate: fundamental balance sheet solvency and DCF cash flow conservatism determine what to buy, while classical technical momentum dictates when to execute. Neither discipline trades in isolation.",
  }
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

function getTwinAgentInfo(agentId: string): { twinId: string; isTwinRules: boolean; duelPairKey: string } {
  const map: Record<string, { twinId: string; isTwinRules: boolean; duelPairKey: string }> = {
    simons: { twinId: 'baseline-simons-rules', isTwinRules: true, duelPairKey: 'simons' },
    'baseline-simons-rules': { twinId: 'simons', isTwinRules: false, duelPairKey: 'simons' },
    lynch: { twinId: 'baseline-lynch-rules', isTwinRules: true, duelPairKey: 'lynch' },
    'baseline-lynch-rules': { twinId: 'lynch', isTwinRules: false, duelPairKey: 'lynch' },
    marks: { twinId: 'baseline-marks-rules', isTwinRules: true, duelPairKey: 'marks' },
    'baseline-marks-rules': { twinId: 'marks', isTwinRules: false, duelPairKey: 'marks' },
    jhunjhunwala: { twinId: 'baseline-rj-rules', isTwinRules: true, duelPairKey: 'jhunjhunwala' },
    'baseline-rj-rules': { twinId: 'jhunjhunwala', isTwinRules: false, duelPairKey: 'jhunjhunwala' },
    varsity: { twinId: 'baseline-varsity-rules', isTwinRules: true, duelPairKey: 'varsity' },
    'stockminds-core': { twinId: 'baseline-varsity-rules', isTwinRules: true, duelPairKey: 'varsity' },
    'baseline-varsity-rules': { twinId: 'varsity', isTwinRules: false, duelPairKey: 'varsity' },
  };
  return map[agentId] || { twinId: 'simons', isTwinRules: false, duelPairKey: 'simons' };
}

type TabType = 'holdings' | 'performance' | 'watchlist' | 'intel';

export default function Portfolio() {
  const { id, agentId } = useParams<{ id?: string; agentId?: string }>();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  // Active Tab synchronized to URL search params (default: holdings)
  const currentTab = (searchParams.get('tab') as TabType) || 'holdings';
  const setActiveTab = (tab: TabType) => {
    setSearchParams({ tab });
  };

  // Canonicalize route param
  const routeParam = id || agentId || 'simons';
  const currentAgentId = (routeParam === 'stockminds-core' ? 'varsity' : routeParam) as AgentId;

  const [agent, setAgent] = useState<AgentLeaderboardEntry | null>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
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

  const [showPendingOrders, setShowPendingOrders] = useState(false);

  useEffect(() => {
    let isSubscribed = true;

    async function loadPortfolioData(isBackground = false) {
      if (!isBackground) setLoading(true);
      try {
        const [board, pos, ord, mem, nav, wl] = await Promise.all([
          apiService.getLeaderboard(),
          apiService.getAgentPositions(currentAgentId),
          apiService.getAgentOrders(currentAgentId),
          apiService.getAgentMemory(currentAgentId),
          apiService.getAgentNavHistory(),
          apiService.getAgentWatchlist(currentAgentId),
        ]);

        if (!isSubscribed) return;
        const currentAgent = board.find((a: AgentLeaderboardEntry) => a.id === currentAgentId) || null;
        setAgent(currentAgent);
        setPositions(pos);
        setOrders(ord);
        setHeuristics(mem);
        setNavHistory(nav);
        setWatchlist(wl);
      } catch (err) {
        console.warn('Failed to load agent portfolio details:', err);
      } finally {
        if (isSubscribed && !isBackground) setLoading(false);
      }
    }

    loadPortfolioData(false);

    // Dynamic background polling on synchronized cadence (10 min) to keep LTP and intraday metrics fresh
    const pollInterval = setInterval(() => {
      loadPortfolioData(true);
    }, TELEMETRY_POLL_INTERVAL_MS);

    return () => {
      isSubscribed = false;
      clearInterval(pollInterval);
    };
  }, [currentAgentId, isMock]);

  // Session date derived dynamically from open trades or latest NAV history
  const sessionDate = useMemo(() => {
    const latestPosDate = positions.find((p) => p.openedAt)?.openedAt;
    if (latestPosDate) {
      return latestPosDate.split('T')[0];
    }
    if (navHistory.length > 0) {
      return navHistory[navHistory.length - 1].date;
    }
    return new Date().toISOString().split('T')[0];
  }, [navHistory, positions]);

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-28 flex justify-center items-center">
        <div className="flex items-center gap-3 text-zinc-500 font-mono text-xs">
          <div className="w-4 h-4 border-2 border-accent border-t-transparent rounded-full animate-spin" />
          <span>Synchronizing strategy ledger telemetry...</span>
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

  // Financial metrics
  const startingCapitalPaise = agent?.startingCapitalPaise ?? 50000000;
  const currentInvestedPaise = positions
    .filter((p) => p.status === 'OPEN')
    .reduce((sum, p) => sum + p.quantity * p.currentPricePaise, 0);

  const totalNavPaise = agent?.navPaise ?? (startingCapitalPaise + currentInvestedPaise);
  const totalReturnPct = agent?.returnPct ?? ((totalNavPaise - startingCapitalPaise) / startingCapitalPaise) * 100;
  const alphaPct = agent?.alphaVsBenchmarkPct ?? totalReturnPct;

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
  const twinInfo = getTwinAgentInfo(currentAgentId);

  // Dual-curve points
  const dualCurvePoints = (() => {
    const key = getNavKeyForAgent(currentAgentId);
    if (navHistory.length > 0) {
      const pts = navHistory.map((pt) => {
        const rawRupees = (pt as any)[key] ?? 500000;
        const portfolioValuePaise = Math.round(rawRupees * 100);
        return {
          date: pt.date,
          portfolioValuePaise,
          investedCapitalPaise: startingCapitalPaise,
        };
      });

      // Synchronize latest live session NAV with current intraday telemetry
      const lastPt = pts[pts.length - 1];
      if (lastPt.date !== sessionDate) {
        pts.push({
          date: sessionDate,
          portfolioValuePaise: totalNavPaise,
          investedCapitalPaise: startingCapitalPaise,
        });
      } else {
        lastPt.portfolioValuePaise = totalNavPaise;
      }
      return pts;
    }

    return [
      { date: 'Day 0', portfolioValuePaise: startingCapitalPaise, investedCapitalPaise: startingCapitalPaise },
      { date: sessionDate, portfolioValuePaise: totalNavPaise, investedCapitalPaise: startingCapitalPaise },
    ];
  })();

  const latestNavPoint = dualCurvePoints.length > 0 ? dualCurvePoints[dualCurvePoints.length - 1] : null;
  const prevNavPoint = dualCurvePoints.length > 1 ? dualCurvePoints[dualCurvePoints.length - 2] : null;
  const portfolioDayChangePaise = prevNavPoint && latestNavPoint
    ? latestNavPoint.portfolioValuePaise - prevNavPoint.portfolioValuePaise
    : Math.round(totalNavPaise * 0.0025);
  const portfolioDayChangePct = prevNavPoint && prevNavPoint.portfolioValuePaise > 0
    ? (portfolioDayChangePaise / prevNavPoint.portfolioValuePaise) * 100
    : 0.25;

  const llmAgents = AGENT_CATALOG.filter((a) => !a.isRules);
  const rulesAgents = AGENT_CATALOG.filter((a) => a.isRules);
  const openPositionsCount = positions.filter((p) => p.status === 'OPEN').length;
  const closedPositionsCount = positions.filter((p) => p.status === 'CLOSED').length;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6 animate-hero-entrance font-sans">

      {/* 1. TOP HEADER & UNIFIED TWIN BENCHMARK BRIDGE */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 border-b border-border-hairline pb-4">
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-2xl sm:text-3xl font-serif font-medium tracking-tight text-white">
              {cleanAgentName}
            </h1>
            <CategoryBadge type={isRulesControl ? 'RULES' : 'LLM'} />
            <span className="text-zinc-600 hidden sm:inline">·</span>
            <span className="text-xs font-mono text-zinc-400">
              Horizon: <strong className="text-zinc-200 font-normal">{personaProfile.horizon}</strong>
            </span>
          </div>
          <p className="text-xs text-zinc-400 font-sans">
            {personaProfile.school}
          </p>
        </div>

        {/* Action Controls: 1-Click Twin Switcher & Deduplicated 'Switch Agent ▾' */}
        <div className="flex items-center gap-2.5 self-start sm:self-auto flex-wrap">
          {/* Twin Benchmark Bridge Button */}
          <button
            type="button"
            onClick={() => navigate(`/portfolio/${twinInfo.twinId}?tab=${currentTab}`)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-white/[0.04] hover:bg-white/[0.08] text-zinc-300 hover:text-white border border-border-hairline transition-colors text-xs font-mono cursor-pointer"
            title={`Switch to paired ${twinInfo.isTwinRules ? 'deterministic rules control' : 'autonomous LLM strategy'}`}
          >
            <span>⮂ Switch to {twinInfo.isTwinRules ? 'Rules Twin' : 'LLM Agent'}</span>
          </button>

          {/* Head-to-Head Duel Shortcut */}
          <Link
            to={`/comparison`}
            className="hidden sm:inline-flex items-center gap-1 px-2.5 py-1.5 rounded bg-transparent hover:bg-white/[0.04] text-zinc-400 hover:text-accent border border-transparent hover:border-border-hairline transition-colors text-xs font-mono"
            title="Inspect Head-to-Head Duel Comparison"
          >
            <span>Duel</span>
            <ExternalLink className="w-3 h-3 text-zinc-500" />
          </Link>

          {/* Deduplicated Agent Switcher Trigger */}
          <div className="relative" ref={dropdownRef}>
            <button
              type="button"
              onClick={() => setDropdownOpen(!dropdownOpen)}
              className="flex items-center gap-2 bg-[#161616] border border-border-hairline hover:border-white/25 rounded px-3 py-1.5 font-mono text-xs cursor-pointer transition-colors text-zinc-300 hover:text-white"
            >
              <span>Switch Agent</span>
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
                          navigate(`/portfolio/${ag.id}?tab=${currentTab}`);
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
                          navigate(`/portfolio/${ag.id}?tab=${currentTab}`);
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
      </div>

      {/* Persona Mandate Prose (Increased Font Size for Optimal Readability) */}
      <p className="text-sm sm:text-base font-sans text-zinc-300 leading-relaxed max-w-4xl -mt-1">
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

      {/* 3. PRIMARY TABBED WORKSPACE CONTROLS */}
      <div className="flex items-center gap-1 border-b border-border-hairline pb-2 font-mono text-xs overflow-x-auto">
        <button
          onClick={() => setActiveTab('holdings')}
          className={cn(
            "px-4 py-2 rounded-md font-medium transition-colors cursor-pointer flex items-center gap-2 whitespace-nowrap",
            currentTab === 'holdings'
              ? "bg-white/10 text-white border border-white/15"
              : "text-zinc-400 hover:text-white hover:bg-white/[0.03] border border-transparent"
          )}
        >
          <span>Holdings</span>
          <span className="px-1.5 py-0.2 rounded bg-white/10 text-[10px] text-zinc-300">
            {openPositionsCount}
          </span>
        </button>

        <button
          onClick={() => setActiveTab('performance')}
          className={cn(
            "px-4 py-2 rounded-md font-medium transition-colors cursor-pointer flex items-center gap-2 whitespace-nowrap",
            currentTab === 'performance'
              ? "bg-white/10 text-white border border-white/15"
              : "text-zinc-400 hover:text-white hover:bg-white/[0.03] border border-transparent"
          )}
        >
          <span>Performance & Past Trades</span>
          <span className="px-1.5 py-0.2 rounded bg-white/10 text-[10px] text-zinc-300">
            {closedPositionsCount} Closed
          </span>
        </button>

        <button
          onClick={() => setActiveTab('watchlist')}
          className={cn(
            "px-4 py-2 rounded-md font-medium transition-colors cursor-pointer flex items-center gap-2 whitespace-nowrap",
            currentTab === 'watchlist'
              ? "bg-white/10 text-white border border-white/15"
              : "text-zinc-400 hover:text-white hover:bg-white/[0.03] border border-transparent"
          )}
        >
          <span>Watchlist</span>
          <span className="px-1.5 py-0.2 rounded bg-white/10 text-[10px] text-zinc-300">
            {watchlist.length}
          </span>
        </button>

        <button
          onClick={() => setActiveTab('intel')}
          className={cn(
            "px-4 py-2 rounded-md font-medium transition-colors cursor-pointer flex items-center gap-2 whitespace-nowrap",
            currentTab === 'intel'
              ? "bg-white/10 text-white border border-white/15"
              : "text-zinc-400 hover:text-white hover:bg-white/[0.03] border border-transparent"
          )}
        >
          <span>Methodology & Memory</span>
          <span className="px-1.5 py-0.2 rounded bg-white/10 text-[10px] text-zinc-300">
            {heuristics.length} Rules
          </span>
        </button>
      </div>

      {/* 4. TAB CONTENTS */}

      {/* TAB 1: HOLDINGS & CAPITAL (Option A 3-Column Layout with Unified Portfolio Returns) */}
      {currentTab === 'holdings' && (
        <div className="space-y-6 animate-hero-entrance">
          <HoldingsLinearStack
            positions={positions}
            startingCapitalPaise={startingCapitalPaise}
            totalNavPaise={totalNavPaise}
            totalReturnPct={totalReturnPct}
            dayChangePaise={portfolioDayChangePaise}
            dayChangePct={portfolioDayChangePct}
            pendingCount={pendingOrders.length}
          />
        </div>
      )}

      {/* TAB 2: PERFORMANCE & PAST CLOSED TRADES */}
      {currentTab === 'performance' && (
        <div className="space-y-6 animate-hero-entrance">
          {/* Main Trajectory Curve */}
          <div className="bg-[#161616] border border-border-hairline p-5 rounded-lg space-y-4">
            <PortfolioDualCurve
              navPoints={dualCurvePoints}
              color="#818CF8"
              height={260}
            />
          </div>

          {/* Key Quantitative Metrics Strip with Reusable Warm-Up State */}
          <div className="border border-border-hairline bg-[#161616] rounded-lg p-3 sm:p-4 grid grid-cols-2 md:grid-cols-4 divide-y sm:divide-y-0 sm:divide-x divide-border-hairline font-mono text-xs">
            <div className="p-3 sm:px-4">
              <span className="text-[10px] uppercase tracking-wider text-zinc-500 block font-sans">Sharpe Ratio</span>
              <div className="text-xl font-bold text-white mt-1 tabular-nums">
                <WarmupMetric
                  value={agent?.sharpeRatio}
                  closedTrades={agent?.closedTrades ?? 0}
                  formatter={(v) => v.toFixed(2)}
                />
              </div>
            </div>

            <div className="p-3 sm:px-4">
              <span className="text-[10px] uppercase tracking-wider text-zinc-500 block font-sans">Max Drawdown</span>
              <div className="text-xl font-bold text-negative mt-1 tabular-nums">
                <WarmupMetric
                  value={agent?.maxDrawdownPct}
                  closedTrades={agent?.closedTrades ?? 0}
                  formatter={(v) => `-${Math.abs(v).toFixed(2)}%`}
                />
              </div>
            </div>

            <div className="p-3 sm:px-4">
              <span className="text-[10px] uppercase tracking-wider text-zinc-500 block font-sans">Win Rate</span>
              <div className="text-xl font-bold text-white mt-1 tabular-nums">
                <WarmupMetric
                  value={agent?.winRatePct}
                  closedTrades={agent?.closedTrades ?? 0}
                  formatter={(v) => `${(v || 0).toFixed(1)}%`}
                />
              </div>
            </div>

            <div className="p-3 sm:px-4">
              <span className="text-[10px] uppercase tracking-wider text-zinc-500 block font-sans">Alpha vs Nifty 500</span>
              <div
                className={cn(
                  "text-xl font-bold mt-1 tabular-nums",
                  alphaPct >= 0 ? "text-positive" : "text-negative"
                )}
              >
                {alphaPct >= 0 ? '+' : ''}{formatPct(alphaPct)}
              </div>
            </div>
          </div>

          {/* Scrollable List of Past Closed Trades */}
          <ClosedTradesList positions={positions} />
        </div>
      )}

      {/* TAB 3: DEDICATED WATCHLIST TAB */}
      {currentTab === 'watchlist' && (
        <div className="space-y-6 animate-hero-entrance">
          <AgentWatchlistSection
            watchlist={watchlist}
            agentName={cleanAgentName}
            lastRunDate={sessionDate}
          />
        </div>
      )}

      {/* TAB 4: STRATEGY INTEL & MEMORY BANK */}
      {currentTab === 'intel' && (
        <div className="space-y-8 animate-hero-entrance">
          {/* 4-Stage Tapered Screening Funnel */}
          <WatchlistFunnel initialAgentId={currentAgentId} />

          {/* Learned Heuristics Causal Memory Bank */}
          <LearnedMemoryBankSection heuristics={heuristics} />
        </div>
      )}

    </div>
  );
}
