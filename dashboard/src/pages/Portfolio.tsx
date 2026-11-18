import { useState, useEffect, useMemo, useRef } from 'react';
import { useParams, useNavigate, useSearchParams, Link } from 'react-router-dom';
import { ChevronDown, ChevronUp, Check, ExternalLink, ShieldCheck } from 'lucide-react';
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
import { getAgentDisplayName, isRulesStrategy } from '../constants/personas';
import { cn } from '../utils/cn';
import PortfolioDualCurve from '../components/PortfolioDualCurve';
import HoldingsLinearStack from '../components/HoldingsLinearStack';
import ClosedTradesList from '../components/ClosedTradesList';
import LearnedMemoryBankSection from '../components/LearnedMemoryBankSection';
import WatchlistFunnel from '../components/WatchlistFunnel';
import AgentWatchlistSection from '../components/AgentWatchlistSection';
import ExplainabilitySpotlight from '../components/ExplainabilitySpotlight';

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
      "Operating on a quantitative statistical momentum framework, Jimmy identifies confirmed trend breakouts, efficiency ratios, and volume surges across the Nifty 500 universe. Positions are sized mathematically via volatility parity rather than subjective conviction. Stalled or decaying trades are pruned aggressively to continually recycle capital into fresh mathematical edges.",
  },
  lynch: {
    school: 'Growth-at-a-Reasonable-Price (GARP) & Cash Conversion',
    horizon: '30–90 Trading Days',
    description:
      "Operating on a GARP compounding framework, Pete targets understandable franchises with durable operational margins, high return on capital (ROCE), and clean cash conversion (CFO/PAT). Positions are anchored to strict valuation hurdles (PEG <= 1.0) and held through interim market noise to let underlying earnings growth drive returns.",
  },
  marks: {
    school: 'Second-Level Contrarian Value & Margin of Safety',
    horizon: '60–120 Trading Days',
    description:
      "Operating on contrarian value and second-level thinking, Howie hunts for solvent, high-quality businesses experiencing extreme cyclical despair or forced institutional selling. It demands an asymmetric margin of safety, controlling downside risk through deep valuation buffers and sector diversification rather than tight mechanical stop losses.",
  },
  jhunjhunwala: {
    school: 'High-Conviction Structural Growth & Pyramiding',
    horizon: '90–180 Trading Days',
    description:
      "Operating on high-conviction structural compounding in Indian equities, RJ backs ambitious promoters with substantial skin-in-the-game riding multi-year capex and consumption tailwinds. It takes concentrated high-conviction positions and pyramids into winning structural themes, patiently absorbing interim drawdowns to capture multi-quarter upside.",
  },
  varsity: {
    school: 'Textbook Dual-Confluence Investing',
    horizon: '20–75 Trading Days',
    description:
      "Operating on the Varsity dual-confluence framework, this strategy enforces a strict dual mandate: fundamental balance sheet solvency and DCF cash flow conservatism determine what to buy, while classical technical momentum dictates when to execute. Neither discipline trades in isolation.",
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
  { id: 'simons', name: getAgentDisplayName('simons'), isRules: false, strategy: 'Quantitative Statistical Momentum' },
  { id: 'lynch', name: getAgentDisplayName('lynch'), isRules: false, strategy: 'GARP & Cash Conversion' },
  { id: 'marks', name: getAgentDisplayName('marks'), isRules: false, strategy: 'Second-Level Contrarian Value' },
  { id: 'jhunjhunwala', name: getAgentDisplayName('jhunjhunwala'), isRules: false, strategy: 'Structural Growth & Pyramiding' },
  { id: 'varsity', name: getAgentDisplayName('varsity'), isRules: false, strategy: 'Dual-Confluence Swing' },
  // Deterministic Rules Baselines
  { id: 'baseline-simons-rules', name: getAgentDisplayName('baseline-simons-rules'), isRules: true, strategy: 'Quantitative Statistical Momentum' },
  { id: 'baseline-lynch-rules', name: getAgentDisplayName('baseline-lynch-rules'), isRules: true, strategy: 'GARP & Cash Conversion' },
  { id: 'baseline-marks-rules', name: getAgentDisplayName('baseline-marks-rules'), isRules: true, strategy: 'Second-Level Contrarian Value' },
  { id: 'baseline-rj-rules', name: getAgentDisplayName('baseline-rj-rules'), isRules: true, strategy: 'Structural Growth & Pyramiding' },
  { id: 'baseline-varsity-rules', name: getAgentDisplayName('baseline-varsity-rules'), isRules: true, strategy: 'Dual-Confluence Swing' },
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
          <div className="w-4 h-4 border-2 border-brand-blue border-t-transparent rounded-full animate-spin" />
          <span>Synchronizing agents data...</span>
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

  const cleanAgentName = getAgentDisplayName(currentAgentId);

  const personaProfile = getPersonaProfile(currentAgentId);
  const twinInfo = getTwinAgentInfo(currentAgentId);
  const isRules = isRulesStrategy(currentAgentId);
  const basePersonaKey = currentAgentId
    .replace('baseline-', '')
    .replace('-rules', '')
    .replace('rj', 'jhunjhunwala')
    .replace('stockminds-core', 'varsity');

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
            <h1 className="text-2xl sm:text-3xl font-display font-medium tracking-tight text-white">
              {cleanAgentName}
            </h1>
            <CategoryBadge type={isRulesControl ? 'RULES' : 'LLM'} />
            <span className="text-zinc-600 hidden sm:inline">·</span>
            <span className="text-xs font-mono text-zinc-400">
              Horizon: <strong className="text-zinc-200 font-normal">{personaProfile.horizon}</strong>
            </span>
          </div>
          <p className="text-sm text-zinc-400 font-sans">
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
            className="hidden sm:inline-flex items-center gap-1 px-2.5 py-1.5 rounded bg-transparent hover:bg-white/[0.04] text-zinc-400 hover:text-brand-blue-text border border-transparent hover:border-border-hairline transition-colors text-xs font-mono"
            title="Inspect Head-to-Head Duel Comparison"
          >
            <span>Duel</span>
            <ExternalLink className="w-3 h-3 text-zinc-500" />
          </Link>

          {/* Deduplicated Agent Switcher Trigger */}
          <div className="relative" ref={dropdownRef}>
            <button
              type="button"
              aria-haspopup="true"
              aria-expanded={dropdownOpen}
              onClick={() => setDropdownOpen(!dropdownOpen)}
              className="flex items-center gap-2 bg-surface-inset border border-border-hairline hover:border-white/25 rounded px-3 py-1.5 font-mono text-xs cursor-pointer transition-colors text-zinc-300 hover:text-white"
            >
              <span>Switch Agent</span>
              <ChevronDown className={cn("w-3.5 h-3.5 text-zinc-400 transition-transform duration-150", dropdownOpen && "rotate-180")} />
            </button>

            {dropdownOpen && (
              <div className="absolute right-0 top-full mt-1.5 w-72 sm:w-80 bg-surface-inset border border-border-hairline rounded shadow-2xl z-50 py-1 divide-y divide-border-hairline animate-hero-entrance">
                {/* Group 1: Autonomous LLM Agents */}
                <div className="p-1.5 space-y-0.5">
                  <div className="px-2.5 py-1 text-[11px] font-mono text-zinc-500">
                    LLM Agents (5)
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
                        {isSelected && <Check className="w-3.5 h-3.5 text-brand-blue-text flex-shrink-0" />}
                      </button>
                    );
                  })}
                </div>

                {/* Group 2: Deterministic Rules Baselines */}
                <div className="p-1.5 space-y-0.5">
                  <div className="px-2.5 py-1 text-[11px] font-mono text-zinc-500">
                    Rules Baselines (5)
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
                        {isSelected && <Check className="w-3.5 h-3.5 text-brand-blue-text flex-shrink-0" />}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 1.5. STRATEGY IDENTITY & HORIZON PILL BAR (HIGH SCANNABILITY) */}
      {/* <div className="flex flex-wrap items-center justify-between gap-3 font-mono text-xs -mt-1 pb-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="px-2.5 py-1 rounded bg-surface-well border border-border-hairline text-zinc-300">
            <span className="text-zinc-500 mr-1.5">Horizon:</span>
            <strong className="text-zinc-200 font-medium">{personaProfile.horizon}</strong>
          </span>
          <span className="px-2.5 py-1 rounded bg-surface-well border border-border-hairline text-zinc-300">
            <span className="text-zinc-500 mr-1.5">Strategy:</span>
            <strong className="text-zinc-200 font-medium">{personaProfile.school}</strong>
          </span>
          <span className="px-2.5 py-1 rounded bg-surface-well border border-border-hairline text-zinc-400 hidden sm:inline-flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
            <span>Point-in-Time Audited</span>
          </span>
        </div>

        <button
          onClick={() => setActiveTab('intel')}
          className="text-xs font-mono text-brand-blue-text hover:underline cursor-pointer flex items-center gap-1"
        >
          <span>View Mandate & Audit</span>
          <span>→</span>
        </button>
      </div> */}

      {/* 2. PENDING ORDERS STATUS STRIP (IF ANY) */}
      {pendingOrders.length > 0 && (
        <div className="border border-border-hairline bg-surface-inset rounded-lg px-4 py-2.5 font-mono text-xs space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <span className="w-2 h-2 rounded-full bg-brand-blue animate-pulse" />
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
            <div className="overflow-x-auto border border-border-hairline bg-[#161616] rounded-lg mt-2">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-border-hairline text-zinc-400 text-xs sm:text-sm font-mono bg-[#121212] whitespace-nowrap">
                    <th className="py-3 px-3.5 font-normal">Side</th>
                    <th className="py-3 px-3.5 font-normal">Symbol</th>
                    <th className="py-3 px-3.5 font-normal text-right">Shares</th>
                    <th className="py-3 px-3.5 font-normal text-right">Limit Price</th>
                    <th className="py-3 px-3.5 font-normal text-right">Est. Outlay</th>
                    <th className="py-3 px-3.5 font-normal text-right">Queued At</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border-hairline text-base font-sans whitespace-nowrap">
                  {pendingOrders.map((ord, idx) => {
                    const price = ord.limitPricePaise ?? ord.entryLowPaise ?? 0;
                    const estOutlay = ord.quantity * price;
                    return (
                      <tr
                        key={ord.id}
                        className={cn(
                          "transition-colors group hover:bg-white/[0.03]",
                          idx % 2 === 1 ? "bg-white/[0.01]" : "bg-transparent"
                        )}
                      >
                        <td className="py-3 px-3.5">
                          <span className="px-2.5 py-0.5 rounded text-xs font-mono font-semibold uppercase tracking-wider border border-emerald-500/30 text-positive bg-emerald-500/10">
                            {ord.side}
                          </span>
                        </td>
                        <td className="py-3 px-3.5 font-sans font-medium text-base text-zinc-100">{ord.symbol}</td>
                        <td className="py-3 px-3.5 text-right font-mono text-base tabular-nums text-zinc-300">{ord.quantity}</td>
                        <td className="py-3 px-3.5 text-right font-mono text-base tabular-nums text-zinc-200">
                          {formatPaiseToRupees(price)}
                        </td>
                        <td className="py-3 px-3.5 text-right font-mono text-base tabular-nums text-brand-blue-text font-medium">
                          {formatPaiseToRupees(estOutlay)}
                        </td>
                        <td className="py-3 px-3.5 text-right font-mono text-sm text-zinc-400">
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
      <div
        role="tablist"
        aria-label="Portfolio analytical workspaces"
        className="flex items-center gap-1 border-b border-border-hairline pb-2 font-mono text-xs overflow-x-auto"
      >
        <button
          role="tab"
          aria-selected={currentTab === 'holdings'}
          onClick={() => setActiveTab('holdings')}
          className={cn(
            "px-4 py-2 rounded font-medium transition-colors cursor-pointer flex items-center gap-2 whitespace-nowrap",
            currentTab === 'holdings'
              ? "bg-white/10 text-white border border-white/15"
              : "text-zinc-400 hover:text-white hover:bg-white/[0.03] border border-transparent"
          )}
        >
          <span>Holdings</span>
          <span className="px-1.5 py-0.5 rounded bg-white/10 text-[10px] text-zinc-300">
            {openPositionsCount}
          </span>
        </button>

        <button
          role="tab"
          aria-selected={currentTab === 'watchlist'}
          onClick={() => setActiveTab('watchlist')}
          className={cn(
            "px-4 py-2 rounded font-medium transition-colors cursor-pointer flex items-center gap-2 whitespace-nowrap",
            currentTab === 'watchlist'
              ? "bg-white/10 text-white border border-white/15"
              : "text-zinc-400 hover:text-white hover:bg-white/[0.03] border border-transparent"
          )}
        >
          <span>Watchlist</span>
          <span className="px-1.5 py-0.5 rounded bg-white/10 text-[10px] text-zinc-300">
            {watchlist.length}
          </span>
        </button>

        <button
          role="tab"
          aria-selected={currentTab === 'performance'}
          onClick={() => setActiveTab('performance')}
          className={cn(
            "px-4 py-2 rounded font-medium transition-colors cursor-pointer flex items-center gap-2 whitespace-nowrap",
            currentTab === 'performance'
              ? "bg-white/10 text-white border border-white/15"
              : "text-zinc-400 hover:text-white hover:bg-white/[0.03] border border-transparent"
          )}
        >
          <span>Performance & Past Trades</span>
          <span className="px-1.5 py-0.5 rounded bg-white/10 text-[10px] text-zinc-300">
            {closedPositionsCount} Closed
          </span>
        </button>



        {/* <button
          role="tab"
          aria-selected={currentTab === 'intel'}
          onClick={() => setActiveTab('intel')}
          className={cn(
            "px-4 py-2 rounded font-medium transition-colors cursor-pointer flex items-center gap-2 whitespace-nowrap",
            currentTab === 'intel'
              ? "bg-white/10 text-white border border-white/15"
              : "text-zinc-400 hover:text-white hover:bg-white/[0.03] border border-transparent"
          )}
        >
          <span>Audit & Methodology</span>
        </button> */}
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
          <div className="glow-box bg-surface-inset border border-border-hairline p-5 rounded-lg space-y-4">
            <PortfolioDualCurve
              navPoints={dualCurvePoints}
              color="#818CF8"
              height={260}
            />
          </div>

          {/* Key Quantitative Metrics Strip with Reusable Warm-Up State */}
          <div className="glow-box bg-surface-inset border border-border-hairline rounded-lg p-3 sm:p-4 grid grid-cols-2 md:grid-cols-4 divide-y sm:divide-y-0 sm:divide-x divide-border-hairline font-mono text-xs">
            <div className="p-3 sm:px-4">
              <span className="text-[11px] text-zinc-500 block font-sans">Sharpe Ratio</span>
              <div className="text-xl font-bold text-white mt-1 tabular-nums">
                <WarmupMetric
                  value={agent?.sharpeRatio}
                  closedTrades={agent?.closedTrades ?? 0}
                  formatter={(v) => v.toFixed(2)}
                />
              </div>
            </div>

            <div className="p-3 sm:px-4">
              <span className="text-[11px] text-zinc-500 block font-sans">Max Drawdown</span>
              <div className="text-xl font-bold text-negative mt-1 tabular-nums">
                <WarmupMetric
                  value={agent?.maxDrawdownPct}
                  closedTrades={agent?.closedTrades ?? 0}
                  formatter={(v) => `-${Math.abs(v).toFixed(2)}%`}
                />
              </div>
            </div>

            <div className="p-3 sm:px-4">
              <span className="text-[11px] text-zinc-500 block font-sans">Win Rate</span>
              <div className="text-xl font-bold text-white mt-1 tabular-nums">
                <WarmupMetric
                  value={agent?.winRatePct}
                  closedTrades={agent?.closedTrades ?? 0}
                  formatter={(v) => `${(v || 0).toFixed(1)}%`}
                />
              </div>
            </div>

            <div className="p-3 sm:px-4">
              <span className="text-[11px] text-zinc-500 block font-sans">Alpha vs Nifty 500</span>
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

      {/* TAB 4: STRATEGY INTEL, AUDIT & MEMORY BANK */}
      {currentTab === 'intel' && (
        <div className="space-y-8 animate-hero-entrance">
          {/* 1. Forensic Reasoning & Ground-Truth Verification */}
          {!isRules ? (
            <ExplainabilitySpotlight personaId={basePersonaKey} />
          ) : (
            <div className="border border-border-hairline bg-surface-inset rounded-lg p-5 font-mono text-xs text-zinc-400 space-y-2">
              <div className="flex items-center gap-2 text-white font-medium text-sm">
                <ShieldCheck className="w-4 h-4 text-emerald-400" />
                <span>Deterministic Python Control · Zero Hallucination Risk</span>
              </div>
              <p className="text-zinc-300 font-sans leading-relaxed text-sm">
                This strategy is a deterministic control baseline executing fixed numerical rules in Python. It has no generative LLM reasoning layer and therefore zero citation hallucination risk.
              </p>
            </div>
          )}

          {/* 2. Detailed Investment Philosophy & Execution Mandate Dossier */}
          <div className="border border-border-hairline bg-surface-inset rounded-lg p-5 sm:p-6 space-y-3 font-sans">
            <div className="flex items-center justify-between border-b border-border-hairline pb-3">
              <h3 className="font-display font-medium text-base sm:text-lg text-white">
                Investment Philosophy & Execution Mandate
              </h3>
              <span className="font-mono text-xs text-brand-blue-text bg-brand-blue-soft border border-brand-blue/30 px-2.5 py-0.5 rounded font-medium">
                {personaProfile.horizon}
              </span>
            </div>
            <p className="text-sm sm:text-base text-zinc-300 leading-relaxed font-sans">
              {personaProfile.description}
            </p>
          </div>

          {/* 3. 4-Stage Tapered Screening Funnel */}
          <WatchlistFunnel initialAgentId={currentAgentId} />

          {/* 4. Learned Heuristics Causal Memory Bank */}
          <LearnedMemoryBankSection heuristics={heuristics} />
        </div>
      )}

    </div>
  );
}
