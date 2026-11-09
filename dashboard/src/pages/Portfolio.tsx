import { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import type {
  AgentId,
  AgentLeaderboardEntry,
  Position,
  Order,
  Decision,
  HeuristicMemory,
  NavHistoryPoint,
} from '../types';
import { apiService, getIsMockMode, setMockMode } from '../services/api';
import { formatPaiseToRupees, formatPct } from '../utils/formatters';
import PortfolioDualCurve from '../components/PortfolioDualCurve';
import HoldingsLinearStack from '../components/HoldingsLinearStack';
import IntegratedTradesSection from '../components/IntegratedTradesSection';
import LearnedMemoryBankSection from '../components/LearnedMemoryBankSection';
import WatchlistFunnel from '../components/WatchlistFunnel';

interface PersonaProfile {
  school: string;
  horizon: string;
  inspiration: string;
  description: string;
}

const PERSONA_PROFILES: Record<string, PersonaProfile> = {
  simons: {
    school: 'Quantitative Statistical Momentum & Volatility Parity',
    horizon: '1–10 Trading Days',
    inspiration: 'Jim Simons (Renaissance Technologies)',
    description:
      "Modeled on Jim Simons's systematic framework at Renaissance Technologies, this agent identifies confirmed statistical momentum breakouts, trend efficiency, and volume surges across the Nifty 500 universe. Positions are sized mathematically via volatility parity rather than subjective conviction. Stalled or decaying trades are pruned aggressively to continually recycle capital into fresh mathematical edges.",
  },
  lynch: {
    school: 'Growth-at-a-Reasonable-Price (GARP) & Cash Conversion',
    horizon: '15–60 Trading Days',
    inspiration: 'Peter Lynch (Fidelity Magellan)',
    description:
      "Embodying Peter Lynch's classic GARP methodology (One Up On Wall Street), this agent targets understandable compounding franchises with durable operational margins, high return on capital (ROCE), and clean cash conversion (CFO/PAT). Positions are anchored to strict valuation hurdles (PEG <= 1.0) and held through interim market noise to let underlying earnings growth drive returns.",
  },
  marks: {
    school: 'Second-Level Contrarian Value & Margin of Safety',
    horizon: '30–90 Trading Days',
    inspiration: 'Howard Marks (Oaktree Capital)',
    description:
      "Rooted in Howard Marks's second-level thinking (The Most Important Thing), this agent hunts for solvent, high-quality businesses experiencing extreme cyclical despair or forced institutional selling. It demands an asymmetric margin of safety, controlling downside risk through deep valuation buffers and sector diversification rather than tight mechanical stop losses.",
  },
  jhunjhunwala: {
    school: 'High-Conviction Structural Growth & Pyramiding',
    horizon: '90–180 Trading Days',
    inspiration: 'Rakesh Jhunjhunwala (Rare Enterprises)',
    description:
      "Inspired by Rakesh Jhunjhunwala's compounding philosophy in Indian equities, this agent backs ambitious promoters with substantial skin-in-the-game riding multi-year capex and consumption tailwinds. It takes concentrated high-conviction positions and pyramids into winning structural themes, patiently absorbing interim drawdowns to capture multi-quarter upside.",
  },
  'stockminds-core': {
    school: 'Dual-Confluence Swing & DCF Margin-of-Safety',
    horizon: '5–20 Trading Days',
    inspiration: 'Zerodha Varsity (Karthik Rangappa)',
    description:
      "Operating on the Zerodha Varsity framework (Modules 2, 3, and 9), this agent enforces a strict dual-confluence mandate: fundamental balance sheet solvency and DCF cash flow conservatism determine what to buy, while classical technical momentum (EMA stacks and pullback support) dictates when to execute. Neither discipline trades in isolation.",
  },
  varsity: {
    school: 'Dual-Confluence Swing & DCF Margin-of-Safety',
    horizon: '5–20 Trading Days',
    inspiration: 'Zerodha Varsity (Karthik Rangappa)',
    description:
      "Operating on the Zerodha Varsity framework (Modules 2, 3, and 9), this agent enforces a strict dual-confluence mandate: fundamental balance sheet solvency and DCF cash flow conservatism determine what to buy, while classical technical momentum (EMA stacks and pullback support) dictates when to execute. Neither discipline trades in isolation.",
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
      school: `${baseProfile.school} (Algorithmic Control Benchmark)`,
      horizon: baseProfile.horizon,
      inspiration: `Deterministic Control Group · Zero LLM Inference`,
      description: `The non-cognitive scientific control benchmark for the ${baseProfile.inspiration} strategy. It executes the exact mathematical screening thresholds, hard stops, and ranking rules deterministically without LLM inference, prompt reflection, or heuristic adaptation, serving to rigorously isolate the net cognitive alpha added by LLM reasoning.`,
    };
  }

  return baseProfile;
}

const AGENT_LIST = [
  { id: 'simons', name: 'Jim Simons' },
  { id: 'lynch', name: 'Peter Lynch' },
  { id: 'marks', name: 'Howard Marks' },
  { id: 'jhunjhunwala', name: 'Rakesh Jhunjhunwala' },
  { id: 'stockminds-core', name: 'StockMinds Core' },
  { id: 'baseline-simons-rules', name: 'Simons (Rules Baseline)' },
  { id: 'baseline-lynch-rules', name: 'Lynch (Rules Baseline)' },
  { id: 'baseline-marks-rules', name: 'Marks (Rules Baseline)' },
  { id: 'baseline-rj-rules', name: 'Jhunjhunwala (Rules Baseline)' },
  { id: 'baseline-varsity-rules', name: 'Varsity (Rules Baseline)' },
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
  const [navHistory, setNavHistory] = useState<NavHistoryPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [isMock, setIsMock] = useState(getIsMockMode());

  useEffect(() => {
    async function loadData() {
      setLoading(true);
      try {
        const [allAgents, posData, orderData, decData, memData, navData] = await Promise.all([
          apiService.getLeaderboard(),
          apiService.getAgentPositions(currentAgentId),
          apiService.getAgentOrders(currentAgentId),
          apiService.getAgentDecisions(currentAgentId),
          apiService.getAgentMemory(currentAgentId),
          apiService.getAgentNavHistory(),
        ]);

        // Prioritize EXACT ID match first to prevent rules control collision
        const current =
          allAgents.find((a) => a.id === currentAgentId) ||
          allAgents.find(
            (a) =>
              a.id.replace('baseline-', '').replace('-rules', '') === currentAgentId ||
              (currentAgentId === 'varsity' && a.id === 'stockminds-core')
          ) ||
          allAgents[0] ||
          null;

        setAgent(current);
        setPositions(posData);
        setOrders(orderData);
        setDecisions(decData);
        setHeuristics(memData);
        setNavHistory(navData);
      } finally {
        setLoading(false);
      }
    }
    loadData();
    const handleSync = () => {
      setIsMock(getIsMockMode());
      loadData();
    };
    window.addEventListener('mock_mode_changed', handleSync);
    return () => window.removeEventListener('mock_mode_changed', handleSync);
  }, [currentAgentId]);

  const handleToggleMockMode = () => {
    const next = !isMock;
    setIsMock(next);
    setMockMode(next);
  };

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-28 flex justify-center items-center font-mono">
        <div className="flex items-center gap-3 text-zinc-500 text-xs">
          <div className="w-4 h-4 border-2 border-[#D4AF37] border-t-transparent rounded-full animate-spin" />
          <span>Synchronizing strategy telemetry...</span>
        </div>
      </div>
    );
  }

  const activePositions = positions.filter((p) => p.status === 'OPEN');
  const costBasisPaise = activePositions.reduce((acc, p) => acc + p.quantity * p.entryPricePaise, 0);
  const currentInvestedPaise = activePositions.reduce((acc, p) => acc + p.quantity * p.currentPricePaise, 0);
  const totalNavPaise = agent?.navPaise || 10000000;
  const startingCapitalPaise = agent?.startingCapitalPaise || 10000000;
  const cashPaise = Math.max(0, totalNavPaise - currentInvestedPaise);
  const unrealizedPnLPaise = currentInvestedPaise - costBasisPaise;
  const netGainPaise = totalNavPaise - startingCapitalPaise;
  const totalReturnPct = agent?.returnPct !== 0 ? (agent?.returnPct ?? 0) : (netGainPaise / startingCapitalPaise) * 100;
  const alphaPct = agent?.alphaVsBenchmarkPct ?? 0;

  const holdingsWeightPct = totalNavPaise > 0 ? (currentInvestedPaise / totalNavPaise) * 100 : 0;
  const cashWeightPct = totalNavPaise > 0 ? (cashPaise / totalNavPaise) * 100 : 0;

  const isRulesControl =
    currentAgentId.startsWith('baseline-') ||
    currentAgentId.includes('rules') ||
    (agent?.name || '').toLowerCase().includes('rules');

  const cleanAgentName = (agent?.name || currentAgentId)
    .replace(' (LLM)', '')
    .replace(' (Rules Baseline)', '')
    .replace(' (Rules Control)', '');

  const personaProfile = getPersonaProfile(currentAgentId);

  // Build dual-curve points for this agent
  const dualCurvePoints = (() => {
    if (navHistory.length > 0) {
      return navHistory.map((pt) => {
        const key = currentAgentId.replace('baseline-', '').replace('-rules', '');
        const rawVal =
          (pt as any)[currentAgentId] ??
          (pt as any)[key] ??
          (currentAgentId === 'stockminds-core' ? pt.stockmindsCore : undefined) ??
          100000;
        const portfolioValuePaise = rawVal > 2000000 ? rawVal : rawVal * 100;
        const investedCapitalPaise = startingCapitalPaise;

        return {
          date: pt.date,
          portfolioValuePaise,
          investedCapitalPaise,
        };
      });
    }

    const initialPaise = startingCapitalPaise;
    const diff = totalNavPaise - initialPaise;
    return [
      { date: '2026-10-15', portfolioValuePaise: initialPaise, investedCapitalPaise: initialPaise },
      { date: '2026-10-19', portfolioValuePaise: Math.round(initialPaise + diff * 0.3), investedCapitalPaise: initialPaise },
      { date: '2026-10-22', portfolioValuePaise: Math.round(initialPaise + diff * 0.7), investedCapitalPaise: initialPaise },
      { date: '2026-10-26', portfolioValuePaise: totalNavPaise, investedCapitalPaise: initialPaise },
    ];
  })();

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-10 animate-hero-entrance font-sans">
      
      {/* 1. TOP ANCHOR: BACK LINK & STRATEGY SELECTOR & DATA SOURCE TOGGLE */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 border-b border-white/[0.08] pb-4">
        <Link
          to="/leaderboard"
          className="inline-flex items-center gap-2 text-xs font-mono text-zinc-400 hover:text-white transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Strategy Leaderboard</span>
        </Link>

        {/* Strategy Switcher Dropdown & Live API Mode Pill */}
        <div className="flex items-center gap-3 text-xs font-mono">
          <button
            onClick={handleToggleMockMode}
            className={`px-2.5 py-1 rounded text-[11px] font-mono border transition-colors cursor-pointer ${
              !isMock
                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400 font-medium hover:bg-emerald-500/20'
                : 'bg-amber-500/10 border-amber-500/30 text-amber-400 font-medium hover:bg-amber-500/20'
            }`}
            title="Toggle between Live FastAPI backend data and calibrated Mock Fixtures"
          >
            {!isMock ? '● Live Backend API' : '⚡ Mock Fixture'}
          </button>

          <span className="text-zinc-500 uppercase tracking-wider text-[11px] hidden sm:inline">
            Active Strategy:
          </span>
          <select
            value={currentAgentId}
            onChange={(e) => navigate(`/portfolio/${e.target.value}`)}
            className="bg-black border border-white/15 text-white rounded-sm px-3 py-1.5 font-mono text-xs cursor-pointer focus:outline-none focus:border-[#D4AF37]/60"
          >
            {AGENT_LIST.map((ag) => (
              <option key={ag.id} value={ag.id}>
                {ag.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* 2. PERSONA DOSSIER BRIEFING: PHILOSOPHY, WORLDVIEW & DISCIPLINE (2-3 LINE EXPANSION) */}
      <div className="space-y-3 pb-6 border-b border-white/[0.08]">
        <div className="flex flex-wrap items-baseline gap-x-4 gap-y-2">
          <h1 className="text-3xl sm:text-4xl font-display font-medium tracking-tight text-white">
            {cleanAgentName}
          </h1>

          {/* Persona Metadata Badges */}
          <div className="flex flex-wrap items-center gap-2 text-[11px] font-mono">
            <span className="px-2 py-0.5 rounded bg-[#D4AF37]/10 text-[#D4AF37] border border-[#D4AF37]/25 font-medium">
              {personaProfile.school}
            </span>
            <span className="px-2 py-0.5 rounded bg-white/[0.04] text-zinc-400 border border-white/10">
              Horizon: {personaProfile.horizon}
            </span>
            <span className="px-2 py-0.5 rounded bg-white/[0.04] text-zinc-300 border border-white/10">
              {isRulesControl ? 'Control Group: Deterministic' : 'Engine: Autonomous LLM'}
            </span>
          </div>
        </div>

        {/* 2-3 Line Descriptive Overview (Informed by Codebase & Plan) */}
        <p className="text-sm sm:text-[15px] text-zinc-300 font-sans leading-relaxed max-w-4xl">
          {personaProfile.description}
        </p>
      </div>

      {/* 3. HERO: UNIFIED VALUATION CARD (LEFT) & STREAMLINED HOLDINGS STACK (RIGHT) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch">
        
        {/* Left Card: Unified Valuation & Curve (lg:col-span-7 ~58% width, left-aligned) */}
        <div className="lg:col-span-7 bg-white/[0.02] border border-white/[0.08] p-5 sm:p-6 rounded-sm flex flex-col justify-between space-y-5">
          {/* Top: Current NAV & Key Return Deltas */}
          <div className="space-y-3 pb-3 border-b border-white/[0.08]">
            <div className="flex flex-wrap justify-between items-baseline gap-3">
              <div>
                <span className="text-[11px] font-mono uppercase tracking-wider text-zinc-400 block font-sans">
                  Portfolio Valuation
                </span>
                <div className="text-3xl sm:text-4xl font-display font-medium text-white tracking-tight mt-0.5">
                  {formatPaiseToRupees(totalNavPaise)}
                </div>
              </div>

              {/* Net All-Time Return & Rupee Return */}
              <div className="text-right font-mono">
                <span
                  className={`text-sm font-semibold tabular-nums ${
                    totalReturnPct >= 0 ? 'text-emerald-400' : 'text-[#c4553f]'
                  }`}
                >
                  {formatPct(totalReturnPct)}{' '}
                  <span className="text-xs text-zinc-400 font-normal">
                    ({netGainPaise >= 0 ? '+' : ''}{formatPaiseToRupees(netGainPaise)})
                  </span>
                </span>
                <div className="text-[11px] text-zinc-500 mt-0.5 font-sans">
                  Alpha vs Benchmark: <span className={`font-mono ${alphaPct >= 0 ? 'text-emerald-400/90' : 'text-[#c4553f]'}`}>{formatPct(alphaPct)}</span>
                </div>
              </div>
            </div>

            {/* Sub-bar: Transparent Capital Deployment Split */}
            <div className="flex flex-wrap items-center gap-x-5 gap-y-1.5 text-xs font-mono text-zinc-400 pt-1">
              <span>
                Holdings: <strong className="text-white font-medium">{formatPaiseToRupees(currentInvestedPaise)}</strong>{' '}
                <span className="text-zinc-500 text-[11px]">({holdingsWeightPct.toFixed(1)}%)</span>
              </span>
              <span className="text-white/20">·</span>
              <span>
                Cash: <strong className="text-[#D4AF37] font-medium">{formatPaiseToRupees(cashPaise)}</strong>{' '}
                <span className="text-zinc-500 text-[11px]">({cashWeightPct.toFixed(1)}%)</span>
              </span>
              <span className="text-white/20">·</span>
              <span>
                Cost Basis: <strong className="text-zinc-300 font-medium">{formatPaiseToRupees(costBasisPaise)}</strong>
              </span>
              <span className="text-white/20">·</span>
              <span>
                Unrealized:{' '}
                <strong
                  className={`font-semibold ${
                    unrealizedPnLPaise >= 0 ? 'text-emerald-400' : 'text-[#c4553f]'
                  }`}
                >
                  {unrealizedPnLPaise >= 0 ? '+' : ''}{formatPaiseToRupees(unrealizedPnLPaise)}
                </strong>
              </span>
            </div>
          </div>

          {/* Streamlined Dual Growth Curve (Minimalist & Uncluttered) */}
          <div className="py-1">
            <PortfolioDualCurve
              navPoints={dualCurvePoints}
              color={isRulesControl ? '#38BDF8' : '#10B981'}
              height={205}
            />
          </div>

          {/* Essential Institutional Metrics Strip (Clean, 3 Core Stats) */}
          <div className="grid grid-cols-3 gap-3 pt-3 border-t border-white/[0.08] text-center font-mono text-xs">
            <div className="p-2.5 bg-black/40 rounded border border-white/5">
              <span className="text-[10px] text-zinc-500 block uppercase font-sans tracking-wider">Sharpe Ratio</span>
              <span className="font-semibold text-white text-sm mt-0.5 block">{(agent?.sharpeRatio ?? 0).toFixed(2)}</span>
            </div>
            <div className="p-2.5 bg-black/40 rounded border border-white/5">
              <span className="text-[10px] text-zinc-500 block uppercase font-sans tracking-wider">Max Drawdown</span>
              <span className="font-semibold text-zinc-300 text-sm mt-0.5 block">{formatPct(agent?.maxDrawdownPct ?? 0)}</span>
            </div>
            <div className="p-2.5 bg-black/40 rounded border border-white/5">
              <span className="text-[10px] text-zinc-500 block uppercase font-sans tracking-wider">Win Rate</span>
              <span className="font-semibold text-white text-sm mt-0.5 block">{formatPct(agent?.winRatePct ?? 0)}</span>
            </div>
          </div>
        </div>

        {/* Right Card: Holdings Linear Stack (lg:col-span-5 ~42% width) */}
        <div className="lg:col-span-5">
          <HoldingsLinearStack
            positions={positions}
            cashPaise={cashPaise}
            totalNavPaise={totalNavPaise}
          />
        </div>

      </div>

      {/* 3.5 ACTIVE WATCHLIST CANDIDATE FUNNEL */}
      <WatchlistFunnel />

      {/* 4. STANDALONE LEARNED MEMORY BANK (HIGH LEGIBILITY, CAUSAL HEURISTICS) */}
      <LearnedMemoryBankSection heuristics={heuristics} />

      {/* 5. INTEGRATED TRADE EXECUTION & DECISION LEDGER (TRADES + VERBATIM LLM MEMOS) */}
      <IntegratedTradesSection
        positions={positions}
        decisions={decisions}
        orders={orders}
      />

    </div>
  );
}
