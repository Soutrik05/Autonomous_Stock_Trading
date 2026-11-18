import { useState, useEffect, useMemo, useCallback } from 'react';
import {
  ShieldCheck,
  Scale,
  Clock,
  Receipt,
  Database,
  Cpu,
  Filter,
  Brain,
  CheckCircle2,
} from 'lucide-react';
import type { NavHistoryPoint, AgentLeaderboardEntry, ActivityEvent } from '../types';
import { apiService, TELEMETRY_POLL_INTERVAL_MS } from '../services/api';
import { formatISTDateTime } from '../utils/formatters';
import { cn } from '../utils/cn';
import { MetaList } from '../components/ui/MetaList';
import { ActionLink } from '../components/ui/ActionLink';
import { SectionHeader } from '../components/ui/SectionHeader';
import { TrajectoryChart, type TrajectoryChartPoint } from '../components/TrajectoryChart';
import PersonaCard from '../components/PersonaCard';
import TopAgentRow from '../components/TopAgentRow';
import Reveal from '../components/Reveal';

const SCHOOLS_OF_THOUGHT = [
  {
    index: '01',
    name: 'Jim Simons',
    title: 'Quantitative Momentum',
    personaId: 'simons',
    rulesId: 'baseline-simons-rules',
    rulesDisplayName: 'Rules: Simons Control',
    inspiration: 'Renaissance Technologies',
    horizon: '1–10 Days',
    mandate: 'Statistical Trend Efficiency & Volatility Parity',
    profile: 'Identifies high-efficiency directional momentum and volume acceleration. Triggers swift exits and trailing stops immediately upon signal degradation.',
  },
  {
    index: '02',
    name: 'StockMinds Core',
    title: 'Dual Confluence Swing',
    personaId: 'varsity',
    rulesId: 'baseline-varsity-rules',
    rulesDisplayName: 'Rules: Varsity Control',
    inspiration: 'Zerodha Varsity',
    horizon: '5–20 Days',
    mandate: 'Fundamental Solvency & Trend Pullback Confluence',
    profile: 'Demands dual confluence: pristine balance-sheet solvency paired with technical pullback support above the 200 EMA. Rejects trades if either axis fails.',
  },
  {
    index: '03',
    name: 'Peter Lynch',
    title: 'GARP Compounding',
    personaId: 'lynch',
    rulesId: 'baseline-lynch-rules',
    rulesDisplayName: 'Rules: Lynch Control',
    inspiration: 'Fidelity Magellan',
    horizon: '15–60 Days',
    mandate: 'Growth At a Reasonable Price & Capital Productivity',
    profile: 'Selects profitable franchises compounding earnings faster than their valuation multiples, anchored by resilient cash flows and high returns on capital.',
  },
  {
    index: '04',
    name: 'Howard Marks',
    title: 'Contrarian Margin of Safety',
    personaId: 'marks',
    rulesId: 'baseline-marks-rules',
    rulesDisplayName: 'Rules: Marks Control',
    inspiration: 'Oaktree Capital',
    horizon: '30–90 Days',
    mandate: 'Second-Level Value & Asymmetric Risk Buffers',
    profile: 'Screens for cyclical distress, 52-week lows, and excessive pessimism. Enforces deep solvency buffers where downside is insulated by balance-sheet health.',
  },
  {
    index: '05',
    name: 'Rakesh Jhunjhunwala',
    title: 'Secular Domestic Growth',
    personaId: 'jhunjhunwala',
    rulesId: 'baseline-rj-rules',
    rulesDisplayName: 'Rules: RJ Control',
    inspiration: 'Rare Enterprises',
    horizon: '90–180 Days',
    mandate: 'Structural Compounding & Capex Expansion',
    profile: 'Focuses on secular domestic expansion, visionary promoters with substantial skin-in-the-game, and operating leverage poised for multi-year compounding.',
  },
];

const EXPERIMENT_STAGES = [
  {
    step: '01',
    icon: Database,
    title: 'Universe Ingestion',
    detail: 'Daily closing OHLCV, market depth, and corporate filings across Nifty 500.',
    tag: 'NSE EOD',
    isCore: false,
  },
  {
    step: '02',
    icon: Cpu,
    title: 'Feature Engine',
    detail: 'Technical and solvency metrics computed with strict 15:30 EOD cutoff.',
    tag: '0 Lookahead',
    isCore: false,
  },
  {
    step: '03',
    icon: Filter,
    title: 'Candidate Screening',
    detail: 'Quantitative filters isolate 10–12 qualified candidate equities per persona.',
    tag: 'Hurdle Filter',
    isCore: false,
  },
  {
    step: '04',
    icon: Brain,
    title: 'Parallel Decision',
    subtitle: 'Core Arena',
    detail: 'Autonomous LLM agents and deterministic Python rules evaluate candidates simultaneously.',
    tag: 'AI vs Rules',
    isCore: true,
  },
  {
    step: '05',
    icon: CheckCircle2,
    title: 'Audited Execution',
    detail: 'Statutory STT, GST, and slippage deducted; metric citations audited.',
    tag: 'Fills Audited',
    isCore: false,
  },
];

const TRUST_PILLARS = [
  {
    icon: Clock,
    badge: 'STRICT EOD',
    title: 'Zero Lookahead Bias',
    detail: 'Historical price bars sealed at 15:30 IST cutoff. Future price data cannot leak into decision context.',
  },
  {
    icon: Scale,
    badge: '1:1 RATIO',
    title: 'Matched Baselines',
    detail: 'Every LLM persona is paired against Python rules receiving identical candidate bars and starting capital.',
  },
  {
    icon: ShieldCheck,
    badge: '100% AUDIT',
    title: 'Audited Citations',
    detail: 'Every numeric metric cited in agent reasoning memos is independently verified against raw market feeds.',
  },
  {
    icon: Receipt,
    badge: 'EXACT FEES',
    title: 'Statutory Friction',
    detail: 'Real statutory STT, GST, exchange turnover fees, and empirical slippage are deducted from all order fills.',
  },
];

export default function Home() {
  const [navHistory, setNavHistory] = useState<NavHistoryPoint[]>([]);
  const [leaderboard, setLeaderboard] = useState<AgentLeaderboardEntry[]>([]);
  const [recentEvents, setRecentEvents] = useState<ActivityEvent[]>([]);
  const [chartMode, setChartMode] = useState<'COMPOSITE' | 'PERSONAS'>('COMPOSITE');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData(isBackground = false) {
      if (!isBackground) setLoading(true);
      try {
        const [navData, boardData, activityData] = await Promise.all([
          apiService.getAgentNavHistory(),
          apiService.getLeaderboard(),
          apiService.getActivityFeed(),
        ]);
        setNavHistory(navData);
        setLeaderboard(boardData);
        setRecentEvents(activityData.slice(0, 4));
      } catch (err) {
        console.warn('Failed to load observation data:', err);
      } finally {
        if (!isBackground) setLoading(false);
      }
    }

    loadData(false);

    // Dynamic background polling on synchronized cadence (10 min)
    const pollInterval = setInterval(() => {
      loadData(true);
    }, TELEMETRY_POLL_INTERVAL_MS);

    return () => clearInterval(pollInterval);
  }, []);

  // Compute percentage return trajectories from ₹5,00,000 seed (memoized)
  const SEED_NAV = 500000;
  const chartData: TrajectoryChartPoint[] = useMemo(() => {
    return navHistory.map((pt) => {
      const llmAvgNav = (pt.simons + pt.lynch + pt.marks + pt.jhunjhunwala + pt.stockmindsCore) / 5;
      const llmCompositeReturn = ((llmAvgNav - SEED_NAV) / SEED_NAV) * 100;

      const bSimons = pt.baselineSimons ?? pt.simons;
      const bLynch = pt.baselineLynch ?? pt.lynch;
      const bMarks = pt.baselineMarks ?? pt.marks;
      const bRj = pt.baselineRj ?? pt.jhunjhunwala;
      const bVarsity = pt.baselineVarsity ?? pt.stockmindsCore;
      const rulesAvgNav = (bSimons + bLynch + bMarks + bRj + bVarsity) / 5;
      const rulesCompositeReturn = ((rulesAvgNav - SEED_NAV) / SEED_NAV) * 100;

      const niftyReturn = ((pt.nifty500 - SEED_NAV) / SEED_NAV) * 100;

      const simonsReturn = ((pt.simons - SEED_NAV) / SEED_NAV) * 100;
      const marksReturn = ((pt.marks - SEED_NAV) / SEED_NAV) * 100;
      const lynchReturn = ((pt.lynch - SEED_NAV) / SEED_NAV) * 100;

      const dateParts = pt.date.split('-');
      const shortDate = dateParts.length === 3 ? `${dateParts[1]}/${dateParts[2]}` : pt.date;

      return {
        date: shortDate,
        fullDate: pt.date,
        llmComposite: Number(llmCompositeReturn.toFixed(2)),
        rulesComposite: Number(rulesCompositeReturn.toFixed(2)),
        nifty500: Number(niftyReturn.toFixed(2)),
        simons: Number(simonsReturn.toFixed(2)),
        marks: Number(marksReturn.toFixed(2)),
        lynch: Number(lynchReturn.toFixed(2)),
      };
    });
  }, [navHistory]);

  const handleModeChange = useCallback((mode: 'COMPOSITE' | 'PERSONAS') => {
    setChartMode(mode);
  }, []);

  // Top 3 agents today for live standings strip
  const topAgents = useMemo(() => {
    return [...leaderboard].sort((a, b) => b.returnPct - a.returnPct).slice(0, 3);
  }, [leaderboard]);

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-28 flex justify-center items-center font-mono text-xs text-zinc-500">
        <div className="flex items-center gap-3">
          <div className="w-4 h-4 border-2 border-brand-blue border-t-transparent rounded-full animate-spin" />
          <span>Synchronizing empirical observation deck...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-10 space-y-12 sm:space-y-14 animate-hero-entrance font-sans">

      {/* =========================================================================
          SECTION 1 · PARADIGM 1: INSTITUTIONAL TERMINAL (INTEGRATED GRID CANVAS)
          [Monolithic hairline-bordered container with zero detached floating cards]
          [Left: Masthead thesis, narrative, 4-point protocol matrix, action links]
          [Right: Cumulative return plot + seamlessly docked Top 3 standings strip]
          ========================================================================= */}
      <div className="glow-box rounded-lg">
      <section className="bg-surface-inset border border-border-hairline rounded-lg overflow-hidden">
        <div className="grid grid-cols-1 lg:grid-cols-12 divide-y lg:divide-y-0 lg:divide-x divide-border-hairline">

          {/* Left Column: Editorial Thesis, Protocol Matrix & Primary CTAs */}
          <Reveal mode="immediate" delayMs={0} className="lg:col-span-5 p-6 sm:p-8 lg:p-9 flex flex-col justify-between space-y-7">
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-brand-blue flex-shrink-0 animate-ping opacity-75" />
                <MetaList
                  items={[
                    { label: 'Trial', value: 'Live Paper Trading' },
                    { label: 'Universe', value: 'NSE Nifty 500' },
                  ]}
                  className="text-[11px]"
                />
              </div>

              <h1 className="hero-headline text-white">
                Can AI judgment survive a <span className="hl">live market</span>?
              </h1>

              <p className="text-base sm:text-lg text-zinc-300 font-sans leading-relaxed pt-1">
                Five autonomous LLM agents trade Indian equities live alongside matched, deterministic Python rules. Each pair embodies a distinct investing school of thought—pitted under identical capital and statutory friction to measure whether generative judgment outperforms mechanical execution.
              </p>
            </div>

            {/* Edge-Ruled Key-Value Protocol Ledger */}
            <div className="space-y-2.5 py-4 border-y border-white/[0.08]">
              {[
                { label: 'Universe', value: 'NSE Nifty 500 Index' },
                { label: 'Cohort', value: '10 Agents · 5 Philosophies' },
                { label: 'Lookahead', value: 'Zero · Strict EOD Cutoff' },
                { label: 'Execution', value: 'Audited Fills (STT, Slippage)' },
              ].map(({ label, value }) => (
                <div key={label} className="flex items-baseline gap-3 text-xs sm:text-sm font-mono">
                  <span className="text-zinc-500 flex-shrink-0 w-20 sm:w-24">{label}</span>
                  <span className="w-px h-3 bg-white/10 flex-shrink-0 self-center" />
                  <span className="text-zinc-200">{value}</span>
                </div>
              ))}
            </div>

            {/* Navigation Action Links */}
            <div className="pt-1 flex flex-wrap items-center gap-6 text-sm font-sans font-medium">
              <ActionLink to="/leaderboard" variant="primary">
                Explore Standings Table
              </ActionLink>

              <ActionLink to="/comparison" variant="secondary">
                Inspect Philosophy Matchups
              </ActionLink>
            </div>
          </Reveal>

          {/* Right Column: Integrated Telemetry Deck (Chart + Docked Top 3 Standings) */}
          <Reveal mode="immediate" delayMs={150} className="lg:col-span-7 flex flex-col divide-y divide-border-hairline bg-[#141414]">

            {/* Upper Chamber: Memoized Observed Cumulative Return Trajectories */}
            <TrajectoryChart
              data={chartData}
              mode={chartMode}
              onModeChange={handleModeChange}
            />

            {/* Lower Chamber: Docked Top 3 Standings Strip */}
            <div className="p-5 sm:p-6 space-y-3 font-mono text-xs bg-surface-well">
              <div className="flex items-center justify-between border-b border-white/[0.06] pb-2 text-[11px]">
                <span className="font-medium text-zinc-400">
                  Live Standings · Top 3 Agents Today
                </span>
                <span className="text-zinc-500 text-[10px]">Daily MTM</span>
              </div>

              {/* Vertical Ranked Rows with Hairline Dividers */}
              <div className="divide-y divide-white/[0.04]">
                {topAgents.map((ag, i) => (
                  <TopAgentRow key={ag.id} agent={ag} rank={i} delayMs={200 + i * 380} />
                ))}
              </div>

              {/* Docked Status Footer */}
              <div className="pt-2 border-t border-white/[0.06] flex items-center justify-between text-[10px] text-zinc-500">
                <span>Continuous Public Benchmark</span>
                <span className="text-zinc-400">EOD Cadence · NSE Close</span>
              </div>
            </div>

          </Reveal>

        </div>
      </section>
      </div>


      {/* =========================================================================
          SECTION 2 · THE EXPERIMENT PIPELINE (CONNECTED WORKFLOW NODES)
          [Interactive cards with icons, step indices, subtle hover lift & core highlight]
          ========================================================================= */}
      <Reveal as="section" className="pt-8 sm:pt-10 border-t border-border-hairline space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-baseline justify-between gap-2">
          <SectionHeader
            title="The Experiment Pipeline"
            subtitle="Deterministic point-in-time sequence executing daily at NSE close"
          />
          <span className="font-mono text-[11px] text-zinc-500 flex items-center gap-1.5 self-start sm:self-auto">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
            5-Stage Automated Sequence
          </span>
        </div>

        {/* 5-Stage Interactive Card Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3.5">
          {EXPERIMENT_STAGES.map((st, i) => {
            const Icon = st.icon;
            return (
              <div
                key={st.step}
                className={cn(
                  "p-4 rounded-lg border transition-all duration-200 group flex flex-col justify-between space-y-3 relative overflow-hidden",
                  st.isCore
                    ? "border-brand-blue/50 bg-brand-blue-soft/20 hover:border-brand-blue hover:bg-brand-blue-soft/30 shadow-[0_0_24px_rgba(30,94,174,0.15)]"
                    : "border-border-hairline bg-surface-inset/70 hover:border-white/20 hover:bg-surface-l1"
                )}
              >
                {/* Header row: Step & Icon */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className={cn(
                      "font-mono text-xs font-bold",
                      st.isCore ? "text-brand-blue-text" : "text-zinc-500 group-hover:text-zinc-300"
                    )}>
                      {st.step}
                    </span>
                    <span className="w-1 h-1 rounded-full bg-white/20" />
                    <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-wider">
                      {st.tag}
                    </span>
                  </div>
                  <div className={cn(
                    "w-7 h-7 rounded flex items-center justify-center transition-colors",
                    st.isCore
                      ? "bg-brand-blue-soft text-brand-blue-text border border-brand-blue/40"
                      : "bg-white/[0.03] text-zinc-400 group-hover:text-white border border-white/5"
                  )}>
                    <Icon className="w-3.5 h-3.5" />
                  </div>
                </div>

                {/* Content */}
                <div className="space-y-1.5">
                  <h3 className={cn(
                    "font-sans text-sm font-semibold tracking-tight",
                    st.isCore ? "text-white" : "text-zinc-200 group-hover:text-white"
                  )}>
                    {st.title}
                  </h3>

                  {st.subtitle && (
                    <span className="inline-block px-1.5 py-0.2 rounded text-[10px] font-mono font-medium text-brand-blue-text bg-brand-blue-soft border border-brand-blue/40">
                      {st.subtitle}
                    </span>
                  )}

                  <p className="text-xs text-zinc-400 leading-relaxed font-sans pt-0.5">
                    {st.detail}
                  </p>
                </div>

                {/* Bottom stage connector bar */}
                <div className="pt-2 border-t border-white/[0.04] flex items-center justify-between text-[10px] font-mono text-zinc-500">
                  <span>Stage {i + 1} of 5</span>
                  {i < 4 ? (
                    <span className="text-zinc-600 group-hover:text-zinc-400 transition-colors">Next →</span>
                  ) : (
                    <span className="text-emerald-500 font-medium">Fills Audited ✓</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </Reveal>


      {/* =========================================================================
          SECTION 3 · BUILT FOR RIGOR (INTERACTIVE AUDIT CARDS)
          ========================================================================= */}
      <Reveal as="section" className="pt-8 sm:pt-10 border-t border-border-hairline space-y-6">
        <SectionHeader
          title="Built for Rigor"
          subtitle="Non-negotiable empirical safeguards ensuring authentic out-of-sample validity"
        />

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {TRUST_PILLARS.map((tp, i) => {
            const Icon = tp.icon;
            return (
              <div
                key={tp.title}
                className="p-5 rounded-lg border border-border-hairline bg-surface-inset/60 hover:bg-surface-l1 hover:border-brand-blue/30 transition-all duration-200 group flex flex-col justify-between space-y-4 hover:-translate-y-0.5"
              >
                <div className="flex items-center justify-between">
                  <div className="w-9 h-9 rounded bg-white/[0.03] border border-white/10 flex items-center justify-center text-brand-blue-text group-hover:border-brand-blue/50 group-hover:text-white transition-colors">
                    <Icon className="w-4 h-4" />
                  </div>
                  <span className="font-mono text-[10px] font-medium text-zinc-400 px-2 py-0.5 rounded bg-white/[0.03] border border-white/5">
                    {tp.badge}
                  </span>
                </div>

                <div className="space-y-1.5">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs text-zinc-500">0{i + 1}</span>
                    <h3 className="font-sans text-sm font-semibold text-white group-hover:text-brand-blue-text transition-colors">
                      {tp.title}
                    </h3>
                  </div>
                  <p className="text-xs text-zinc-400 font-sans leading-relaxed">
                    {tp.detail}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </Reveal>


      {/* =========================================================================
          SECTION 4 · THE CORE RESEARCH INQUIRIES (DUAL INTERACTIVE HYPOTHESIS BOXES)
          [Concise one-liners, interactive hover cards, subtle glow, clear CTAs]
          ========================================================================= */}
      <Reveal as="section" className="pt-8 sm:pt-10 border-t border-border-hairline space-y-6">
        <SectionHeader
          title="The Core Research Inquiries"
          subtitle="Empirical hypotheses evaluated under strict out-of-sample discipline"
        />

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Question Box 01 */}
          <div className="p-6 sm:p-7 rounded-lg border border-border-hairline bg-surface-inset hover:border-brand-blue/40 hover:bg-surface-l1 transition-all duration-300 group hover:-translate-y-1 relative overflow-hidden flex flex-col justify-between space-y-6">
            <div className="absolute -right-10 -top-10 w-32 h-32 bg-brand-blue-soft/30 blur-2xl pointer-events-none rounded-full opacity-0 group-hover:opacity-100 transition-opacity" />

            <div className="space-y-4 relative z-10">
              <div className="flex items-center justify-between">
                <span className="px-2 py-0.5 rounded font-mono text-[11px] font-semibold text-brand-blue-text bg-brand-blue-soft border border-brand-blue/30">
                  INQUIRY 01 · ALPHA VALIDITY
                </span>
                <span className="text-[11px] font-mono text-zinc-500">Live Paper Trading</span>
              </div>

              <h3 className="font-display text-2xl sm:text-[26px] font-medium tracking-tight text-white leading-snug group-hover:text-brand-blue-text transition-colors">
                Can Autonomous Agent Personas Generate Real Equity Alpha?
              </h3>

              <div className="p-3.5 rounded bg-surface-well/80 border border-white/[0.06] space-y-1.5">
                <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500 block">Core Mandate</span>
                <p className="text-sm text-zinc-200 font-sans leading-relaxed">
                  Testing whether generative LLM reasoning independently uncovers profitable market anomalies and executes disciplined trades without human intervention.
                </p>
              </div>

              {/* Protocol Spec Badges */}
              <div className="flex flex-wrap gap-2 pt-1 font-mono text-[11px]">
                <span className="px-2 py-1 rounded bg-white/[0.03] text-zinc-400 border border-white/5">
                  5 Diverse Personas
                </span>
                <span className="px-2 py-1 rounded bg-white/[0.03] text-zinc-400 border border-white/5">
                  Point-in-Time Fills
                </span>
                <span className="px-2 py-1 rounded bg-white/[0.03] text-zinc-400 border border-white/5">
                  Audited Citations
                </span>
              </div>
            </div>

            <div className="pt-4 border-t border-white/[0.06] flex items-center justify-between relative z-10">
              <span className="text-xs text-zinc-500 font-mono">Dossiers & Holdings</span>
              <ActionLink to="/portfolio/simons" variant="primary">
                Inspect Persona Portfolios
              </ActionLink>
            </div>
          </div>

          {/* Question Box 02 */}
          <div className="p-6 sm:p-7 rounded-lg border border-border-hairline bg-surface-inset hover:border-brand-blue/40 hover:bg-surface-l1 transition-all duration-300 group hover:-translate-y-1 relative overflow-hidden flex flex-col justify-between space-y-6">
            <div className="absolute -right-10 -top-10 w-32 h-32 bg-brand-blue-soft/30 blur-2xl pointer-events-none rounded-full opacity-0 group-hover:opacity-100 transition-opacity" />

            <div className="space-y-4 relative z-10">
              <div className="flex items-center justify-between">
                <span className="px-2 py-0.5 rounded font-mono text-[11px] font-semibold text-brand-blue-text bg-brand-blue-soft border border-brand-blue/30">
                  INQUIRY 02 · BENCHMARK CONFLUENCE
                </span>
                <span className="text-[11px] font-mono text-zinc-500">Matched Controls</span>
              </div>

              <h3 className="font-display text-2xl sm:text-[26px] font-medium tracking-tight text-white leading-snug group-hover:text-brand-blue-text transition-colors">
                Does Heavy LLM Inference Outperform Matched Rules?
              </h3>

              <div className="p-3.5 rounded bg-surface-well/80 border border-white/[0.06] space-y-1.5">
                <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500 block">Core Mandate</span>
                <p className="text-sm text-zinc-200 font-sans leading-relaxed">
                  Evaluating whether multi-billion-parameter LLM reasoning delivers genuine cognitive excess return over identical, deterministic Python rulebooks.
                </p>
              </div>

              {/* Protocol Spec Badges */}
              <div className="flex flex-wrap gap-2 pt-1 font-mono text-[11px]">
                <span className="px-2 py-1 rounded bg-white/[0.03] text-zinc-400 border border-white/5">
                  1:1 Matched Pairs
                </span>
                <span className="px-2 py-1 rounded bg-white/[0.03] text-zinc-400 border border-white/5">
                  ₹5,00,000 Matched Seed
                </span>
                <span className="px-2 py-1 rounded bg-white/[0.03] text-zinc-400 border border-white/5">
                  Equal Friction
                </span>
              </div>
            </div>

            <div className="pt-4 border-t border-white/[0.06] flex items-center justify-between relative z-10">
              <span className="text-xs text-zinc-500 font-mono">Head-to-Head Alpha</span>
              <ActionLink to="/comparison" variant="primary">
                Compare 5 Matched Pairs
              </ActionLink>
            </div>
          </div>
        </div>
      </Reveal>


      {/* =========================================================================
          SECTION 5 · THE FIVE OBSERVED PERSONAS (CLICKABLE PERSONA CARDS)
          ========================================================================= */}
      <Reveal as="section" className="pt-8 sm:pt-10 border-t border-border-hairline space-y-6">
        <SectionHeader
          title="The Five Observed Personas"
          subtitle="Click any card to open that agent's portfolio and dossier"
        />

        <div className="persona-grid font-sans">
          {SCHOOLS_OF_THOUGHT.map((phi) => (
            <PersonaCard
              key={phi.personaId}
              index={phi.index}
              name={phi.name}
              personaId={phi.personaId}
              inspiration={phi.inspiration}
              horizon={phi.horizon}
              mandate={phi.mandate}
              profile={phi.profile}
            />
          ))}
        </div>

        {/* Bottom-Right Navigation Link */}
        <div className="flex justify-end pt-3 border-t border-white/[0.06]">
          <ActionLink to="/comparison" variant="primary">
            Compare All 5 Schools of Thought
          </ActionLink>
        </div>
      </Reveal>


      {/* =========================================================================
          SECTION 6 · LIVE ACTIVITY FEED (MINIMALIST TERMINAL LOG STREAM)
          [Clean divided rows inside structured card, bottom-right link]
          ========================================================================= */}
      <Reveal as="section" className="pt-8 sm:pt-10 border-t border-border-hairline space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-baseline justify-between gap-2">
          <SectionHeader
            title="Latest Live Activity"
            subtitle="Autonomous order dispatches, simulated broker fills, and audit logs"
          />
          <div className="flex items-center gap-2 font-mono text-[11px] text-zinc-400">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
            <span>Continuous NSE Feed</span>
          </div>
        </div>

        {/* Minimalist Log Stream Box */}
        <div className="glow-box rounded-lg">
        <div className="rounded-lg border border-border-hairline bg-surface-inset divide-y divide-white/[0.05] overflow-hidden font-mono text-xs">
          {recentEvents.length === 0 ? (
            <div className="py-8 text-center text-zinc-500">
              No recent execution events recorded today.
            </div>
          ) : (
            recentEvents.map((evt) => (
              <div
                key={evt.id}
                className="p-3.5 sm:px-5 sm:py-3 flex flex-col sm:flex-row sm:items-center justify-between gap-2 hover:bg-white/[0.02] transition-colors"
              >
                <div className="flex items-center gap-3">
                  <span
                    className={cn(
                      'px-1.5 py-0.5 rounded text-[10px] font-mono font-medium border flex-shrink-0',
                      evt.eventType.includes('FILL')
                        ? 'border-emerald-500/30 text-emerald-400 bg-emerald-500/10'
                        : evt.eventType.includes('EXPIRED')
                          ? 'border-zinc-500/30 text-zinc-400 bg-white/[0.02]'
                          : 'border-brand-blue text-brand-blue-text bg-brand-blue-soft'
                    )}
                  >
                    {evt.eventType}
                  </span>
                  <span className="font-bold text-white">
                    {(evt.agentId || 'SYSTEM').replace('baseline-', '').toUpperCase()}
                  </span>
                  {evt.symbol && (
                    <span className="px-1.5 py-0.2 rounded bg-white/[0.04] text-zinc-300 border border-white/5 font-sans font-medium">
                      {evt.symbol}
                    </span>
                  )}
                  <span className="text-zinc-400 font-sans truncate max-w-[500px]">
                    {evt.message}
                  </span>
                </div>

                <div className="text-[11px] text-zinc-500 flex-shrink-0">
                  {formatISTDateTime(evt.timestamp)}
                </div>
              </div>
            ))
          )}
        </div>
        </div>

        {/* Bottom Navigation */}
        <div className="flex justify-end pt-1">
          <ActionLink to="/pulse" variant="primary">
            Full Activity Ledger
          </ActionLink>
        </div>
      </Reveal>


      {/* =========================================================================
          SECTION 7 · CLOSING VERDICT & PROTOCOL STANDING (TELEMETRY LEDGER)
          ========================================================================= */}
      <Reveal as="section" className="pt-8 sm:pt-10 border-t border-border-hairline">
        <div className="glow-box p-6 sm:p-8 rounded-lg border border-border-hairline bg-surface-inset grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
          
          {/* Left Column: Verdict Narrative */}
          <div className="lg:col-span-7 space-y-4 font-sans">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-brand-blue animate-pulse" />
              <span className="font-mono text-[11px] font-semibold uppercase tracking-wider text-brand-blue-text">
                Protocol Integrity Mandate
              </span>
            </div>

            <h3 className="font-display text-2xl sm:text-3xl font-medium text-white tracking-tight leading-tight">
              Statistical conclusions require 30 round-trip trades per agent.
            </h3>

            <p className="text-sm sm:text-base text-zinc-300 leading-relaxed font-sans max-w-2xl">
              To eliminate regime luck and sample noise, alpha superiority is withheld until 30 closed round-trips are recorded across contrasting macroeconomic cycles. All daily order executions, thesis memos, and cited data remain publicly audited.
            </p>

            <div className="pt-2 flex flex-wrap items-center gap-5 text-sm font-sans font-medium">
              <ActionLink to="/leaderboard" variant="primary">
                Explore Standings Table
              </ActionLink>

              <ActionLink to="/comparison" variant="secondary">
                Inspect Philosophy Matchups
              </ActionLink>

              <ActionLink to="/pulse" variant="secondary">
                System Telemetry & Health
              </ActionLink>
            </div>
          </div>

          {/* Right Column: 3 Metric Telemetry Blocks */}
          <div className="lg:col-span-5 grid grid-cols-3 gap-3 font-mono">
            <div className="p-4 rounded border border-border-hairline bg-surface-well text-center space-y-1">
              <span className="text-[10px] text-zinc-500 uppercase tracking-wider block">Cohort</span>
              <span className="text-xl sm:text-2xl font-bold text-white block">10</span>
              <span className="text-[10px] text-zinc-400 block">5 LLM · 5 Rules</span>
            </div>

            <div className="p-4 rounded border border-border-hairline bg-surface-well text-center space-y-1">
              <span className="text-[10px] text-zinc-500 uppercase tracking-wider block">Regimes</span>
              <span className="text-xl sm:text-2xl font-bold text-brand-blue-text block">411</span>
              <span className="text-[10px] text-zinc-400 block">Market Sessions</span>
            </div>

            <div className="p-4 rounded border border-border-hairline bg-surface-well text-center space-y-1">
              <span className="text-[10px] text-zinc-500 uppercase tracking-wider block">Seed AUM</span>
              <span className="text-xl sm:text-2xl font-bold text-white block">₹50L</span>
              <span className="text-[10px] text-zinc-400 block">₹5L per Agent</span>
            </div>
          </div>

        </div>
      </Reveal>

    </div>
  );
}
