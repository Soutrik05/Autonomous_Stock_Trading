import { useState, useEffect, useMemo } from 'react';
import type { CSSProperties } from 'react';
import { useParams, useSearchParams, Link } from 'react-router-dom';
import { ChevronDown, ChevronUp, ExternalLink, ShieldCheck } from 'lucide-react';
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
import { getAgentLabel } from '../lib/agentNames';
import { getPersonaCopy } from '../lib/personaCopy';
import { useIntroDone } from '../hooks/useIntro';
import { useSpotlightHover } from '../hooks/useSpotlightHover';
import { getCached, setCached } from '../utils/sessionCache';
import { cn } from '../utils/cn';
import PortfolioDualCurve from '../components/PortfolioDualCurve';
import HoldingsLinearStack from '../components/HoldingsLinearStack';
import ClosedTradesList from '../components/ClosedTradesList';
import LearnedMemoryBankSection from '../components/LearnedMemoryBankSection';
import WatchlistFunnel from '../components/WatchlistFunnel';
import AgentWatchlistSection from '../components/AgentWatchlistSection';
import ExplainabilitySpotlight from '../components/ExplainabilitySpotlight';
import AgentSwitchDropdown from '../components/AgentSwitchDropdown';

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

interface PortfolioCache {
  agent: AgentLeaderboardEntry | null;
  leaderboard: AgentLeaderboardEntry[];
  positions: Position[];
  orders: Order[];
  heuristics: HeuristicMemory[];
  navHistory: NavHistoryPoint[];
  watchlist: AgentWatchlistItem[];
}

export default function Portfolio() {
  const { id, agentId } = useParams<{ id?: string; agentId?: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const introDone = useIntroDone();

  // Active Tab synchronized to URL search params (default: holdings)
  const currentTab = (searchParams.get('tab') as TabType) || 'holdings';
  const setActiveTab = (tab: TabType) => {
    setSearchParams({ tab });
  };

  // Canonicalize route param
  const routeParam = id || agentId || 'simons';
  const currentAgentId = (routeParam === 'stockminds-core' ? 'varsity' : routeParam) as AgentId;

  // Remembered so the Comparison page can default to "this agent vs its twin" when it has
  // no ?a=&b= of its own yet.
  useEffect(() => {
    try {
      sessionStorage.setItem('stockminds_last_agent', currentAgentId);
    } catch {
      /* ignore */
    }
  }, [currentAgentId]);

  const [agent, setAgent] = useState<AgentLeaderboardEntry | null>(null);
  const [leaderboard, setLeaderboard] = useState<AgentLeaderboardEntry[]>([]);
  const [positions, setPositions] = useState<Position[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [heuristics, setHeuristics] = useState<HeuristicMemory[]>([]);
  const [navHistory, setNavHistory] = useState<NavHistoryPoint[]>([]);
  const [watchlist, setWatchlist] = useState<AgentWatchlistItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [isMock] = useState(getIsMockMode());

  const [showPendingOrders, setShowPendingOrders] = useState(false);

  // Agent name hover spotlight -- the one shared technique (useSpotlightHover) also used by
  // the header logo and every PageTitle heading.
  const { ref: nameRef, onMouseMove: handleNameMouseMove } = useSpotlightHover<HTMLSpanElement>();

  useEffect(() => {
    let isSubscribed = true;

    // Already have this agent's real data from earlier this session -- show it immediately
    // (no spinner) and just refresh it quietly. A truly never-opened agent has no cache, so
    // the spinner below is only for that genuine first load.
    const cacheKey = `portfolio_${currentAgentId}`;
    const cached = getCached<PortfolioCache>(cacheKey);
    if (cached) {
      setAgent(cached.agent);
      setLeaderboard(cached.leaderboard);
      setPositions(cached.positions);
      setOrders(cached.orders);
      setHeuristics(cached.heuristics);
      setNavHistory(cached.navHistory);
      setWatchlist(cached.watchlist);
      setLoading(false);
    } else {
      setLoading(true);
    }

    async function loadPortfolioData() {
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
        setLeaderboard(board);
        setPositions(pos);
        setOrders(ord);
        setHeuristics(mem);
        setNavHistory(nav);
        setWatchlist(wl);
        setCached<PortfolioCache>(cacheKey, {
          agent: currentAgent,
          leaderboard: board,
          positions: pos,
          orders: ord,
          heuristics: mem,
          navHistory: nav,
          watchlist: wl,
        });
        setCached('leaderboard', board);
      } catch (err) {
        console.warn('Failed to load agent portfolio details:', err);
      } finally {
        if (isSubscribed) setLoading(false);
      }
    }

    loadPortfolioData();

    // Dynamic background polling on synchronized cadence (10 min) to keep LTP and intraday metrics fresh
    const pollInterval = setInterval(() => {
      loadPortfolioData();
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

  const openPositionsCount = positions.filter((p) => p.status === 'OPEN').length;
  const closedPositionsCount = positions.filter((p) => p.status === 'CLOSED').length;

  const terminalCopy = getPersonaCopy(currentAgentId);
  // Twin card name: the one shared "explainer" label helper (agentNames.ts) -- "<Surname>
  // Rules" for a Rules twin, the normal short name for an LLM twin. Also used by the
  // Switch-agent dropdown and the Comparison page, so all three always agree.
  const twinDisplayName = getAgentLabel(twinInfo.twinId);
  const hasTwin = Boolean(twinInfo.twinId) && twinInfo.twinId !== currentAgentId;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6 animate-hero-entrance font-sans">

      {/* 1. AGENT HEADER: identity + plain-English copy (left) and Switch agent + Twin card + Duel (right) */}
      <div className="glow-box bg-surface-inset border border-border-hairline rounded-lg" style={{ padding: '20px 26px' }}>
        <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-6">
          {/* LEFT: name, tags, description */}
          <div className="space-y-2.5 min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-3.5">
              <span
                ref={nameRef}
                onMouseMove={handleNameMouseMove}
                data-text={cleanAgentName}
                style={{
                  '--fs': '48px',
                  fontFamily: "var(--font-headline), 'Red Hat Display Fallback', system-ui, sans-serif",
                  fontWeight: 700,
                  letterSpacing: '-0.02em',
                  lineHeight: 1,
                  color: '#f2efe8',
                  fontSize: 'clamp(28px, 3.6vw, 48px)',
                } as CSSProperties}
                className="name-spotlight"
              >
                {cleanAgentName}
              </span>
              <CategoryBadge type={isRulesControl ? 'RULES' : 'LLM'} />
              <span className="terminal-role-label">
                {terminalCopy.roleTag}
              </span>
            </div>

            <p
              className="text-[17px] text-zinc-300 font-sans max-w-[900px]"
              style={{ lineHeight: 1.55, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}
            >
              {terminalCopy.descBefore}
              <span className="font-semibold" style={{ color: '#10b981' }}>{terminalCopy.highlightName}</span>
              {terminalCopy.descAfter}
            </p>
          </div>

          {/* RIGHT: Switch agent dropdown, Twin card, Duel link */}
          <div className="flex flex-col items-start sm:items-end gap-2.5 flex-shrink-0 w-full sm:w-[250px]">
            <AgentSwitchDropdown highlightIds={[currentAgentId]} currentTab={currentTab} leaderboard={leaderboard} />

            {hasTwin && (
              <Link
                to={`/portfolio/${twinInfo.twinId}?tab=${currentTab}`}
                className="twin-card relative block w-full rounded-lg border border-border-hairline bg-white/[0.03] font-mono"
                style={{ padding: '11px 14px', borderRadius: '12px' }}
                title={`Open ${twinDisplayName}'s portfolio`}
              >
                <span className="absolute top-3 right-3.5 text-zinc-500 text-sm" aria-hidden="true">→</span>
                <div className="text-[10px] text-zinc-500 tracking-wide font-medium mb-1.5">
                  {twinInfo.isTwinRules ? 'RULES TWIN' : 'LLM TWIN'}
                </div>
                <div
                  className="twin-card__name text-white transition-colors duration-200"
                  style={{
                    fontFamily: "var(--font-headline), 'Red Hat Display Fallback', system-ui, sans-serif",
                    fontWeight: 600,
                    fontSize: '16px',
                  }}
                >
                  {twinDisplayName}
                </div>
                <div className="text-[12px] text-zinc-400 font-sans mt-1">
                  {twinInfo.isTwinRules ? 'Same stocks, no AI. Fixed rules only.' : 'Same stocks, with AI judgment.'}
                </div>
              </Link>
            )}

            <Link
              to="/comparison"
              className="inline-flex items-center gap-1 px-1 text-zinc-400 hover:text-brand-blue-text transition-colors text-xs font-mono"
              title="Inspect Head-to-Head Duel Comparison"
            >
              <span>Duel</span>
              <ExternalLink className="w-3 h-3 text-zinc-500" />
            </Link>
          </div>
        </div>
      </div>

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
            key={currentAgentId}
            agentId={currentAgentId}
            introDone={introDone}
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
