import { useState, useEffect, useMemo, useCallback } from 'react';
import {
  ShieldCheck,
  Scale,
  Clock,
  Receipt,
} from 'lucide-react';
import type { NavHistoryPoint, AgentLeaderboardEntry, ActivityEvent } from '../types';
import { apiService } from '../services/api';
import { formatPct, formatISTDateTime } from '../utils/formatters';
import { cn } from '../utils/cn';
import { MetaList } from '../components/ui/MetaList';
import { ActionLink } from '../components/ui/ActionLink';
import { CategoryBadge } from '../components/ui/CategoryBadge';
import { SectionHeader } from '../components/ui/SectionHeader';
import { TrajectoryChart, type TrajectoryChartPoint } from '../components/TrajectoryChart';

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
    title: 'Universe Ingestion',
    detail: 'Daily closing OHLCV, market depth, and balance-sheet filings ingested across the broad investment universe.',
    isCore: false,
  },
  {
    step: '02',
    title: 'Point-in-Time Features',
    detail: 'Technical indicators and fundamental solvency metrics computed at EOD. Zero lookahead bias permitted.',
    isCore: false,
  },
  {
    step: '03',
    title: 'Candidate Screening',
    detail: 'Quantitative screening hurdles filter universe down to 10–12 qualified candidate equities per persona.',
    isCore: false,
  },
  {
    step: '04',
    title: 'Parallel Decision Engines',
    subtitle: 'Core Pivot',
    detail: 'Autonomous LLM agents and deterministic rules evaluate identical candidate data simultaneously under matched capital.',
    isCore: true,
  },
  {
    step: '05',
    title: 'Broker Execution & Audit',
    detail: 'Simulated fills deduct statutory STT, GST, and slippage. Metric citations audited against ground truth.',
    isCore: false,
  },
];

const TRUST_PILLARS = [
  {
    icon: Clock,
    title: 'Zero Lookahead Bias',
    detail: 'Point-in-time indicators computed on historical bars with strict EOD cutoff. Future data cannot leak into decision context.',
  },
  {
    icon: Scale,
    title: 'Matched Control Baselines',
    detail: 'Every LLM persona is paired 1:1 against a deterministic Python rulebook receiving identical candidates and starting capital.',
  },
  {
    icon: ShieldCheck,
    title: 'Audited Metric Citations',
    detail: 'Zero hallucination tolerance. Every metric value cited in an LLM decision memo is independently verified against raw price feeds.',
  },
  {
    icon: Receipt,
    title: 'Real Statutory Friction',
    detail: 'Exact STT, exchange turnover fees, SEBI charges, and empirical slippage are deducted from all order fills. No friction-free illusions.',
  },
];

export default function Home() {
  const [navHistory, setNavHistory] = useState<NavHistoryPoint[]>([]);
  const [leaderboard, setLeaderboard] = useState<AgentLeaderboardEntry[]>([]);
  const [recentEvents, setRecentEvents] = useState<ActivityEvent[]>([]);
  const [chartMode, setChartMode] = useState<'COMPOSITE' | 'PERSONAS'>('COMPOSITE');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
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
        setLoading(false);
      }
    }

    loadData();
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
          <div className="w-4 h-4 border-2 border-accent border-t-transparent rounded-full animate-spin" />
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
      <section className="border border-border-hairline bg-[#161616] rounded-lg overflow-hidden">
        <div className="grid grid-cols-1 lg:grid-cols-12 divide-y lg:divide-y-0 lg:divide-x divide-border-hairline">

          {/* Left Column: Editorial Thesis, Protocol Matrix & Primary CTAs */}
          <div className="lg:col-span-5 p-6 sm:p-8 lg:p-9 flex flex-col justify-between space-y-6">
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-accent flex-shrink-0" />
                <MetaList
                  items={[
                    { label: 'Platform', value: 'Live Paper Trading' },
                    { label: 'Pilot', value: 'NSE Nifty 500' },
                  ]}
                  className="text-[10px]"
                />
              </div>

              <h1 className="font-display text-3xl sm:text-4xl lg:text-[44px] font-medium tracking-tight text-white leading-[1.08]">
                Can AI judgment beat its own rulebook?
              </h1>

              <p className="text-sm sm:text-base text-zinc-300 font-sans leading-relaxed pt-1">
                Five autonomous LLM agents trade India's top equities live alongside matched deterministic rulebooks, each pair personifying a distinct investing philosophy to test whether generative reasoning creates authentic alpha.
              </p>
            </div>

            {/* 4-Point Institutional Protocol Matrix */}
            <div className="grid grid-cols-2 gap-x-4 gap-y-3 py-4 border-y border-white/[0.06] text-xs font-mono">
              <div>
                <span className="text-[10px] uppercase tracking-wider text-zinc-500 block">Universe</span>
                <span className="text-zinc-200 font-sans font-medium mt-0.5 block">NSE Nifty 500</span>
              </div>
              <div>
                <span className="text-[10px] uppercase tracking-wider text-zinc-500 block">Agent Cohort</span>
                <span className="text-zinc-200 font-sans font-medium mt-0.5 block">10 Active (1:1 Matched)</span>
              </div>
              <div>
                <span className="text-[10px] uppercase tracking-wider text-zinc-500 block">Lookahead Bias</span>
                <span className="text-zinc-200 font-sans font-medium mt-0.5 block">Zero (Strict EOD Cutoff)</span>
              </div>
              <div>
                <span className="text-[10px] uppercase tracking-wider text-zinc-500 block">Audit Standard</span>
                <span className="text-zinc-200 font-sans font-medium mt-0.5 block">Public Forensic Ledger</span>
              </div>
            </div>

            {/* Navigation Action Links */}
            <div className="pt-2 flex flex-wrap items-center gap-6 text-sm font-sans font-medium">
              <ActionLink to="/leaderboard" variant="primary">
                Explore Standings Table
              </ActionLink>

              <ActionLink to="/comparison" variant="secondary">
                Inspect Head-to-Head Duels
              </ActionLink>
            </div>
          </div>

          {/* Right Column: Integrated Telemetry Deck (Chart + Docked Top 3 Standings) */}
          <div className="lg:col-span-7 flex flex-col divide-y divide-border-hairline bg-[#141414]">

            {/* Upper Chamber: Memoized Observed Cumulative Return Trajectories */}
            <TrajectoryChart
              data={chartData}
              mode={chartMode}
              onModeChange={handleModeChange}
            />

            {/* Lower Chamber: Docked Top 3 Standings Strip */}
            <div className="p-5 sm:p-6 space-y-3 font-mono text-xs bg-[#121212]">
              <div className="flex items-center justify-between border-b border-white/[0.06] pb-2 text-[11px]">
                <span className="uppercase tracking-wider font-medium text-zinc-400">
                  Live Standings · Top 3 Agents Today
                </span>
                <span className="text-zinc-500 text-[10px]">Daily MTM</span>
              </div>

              {/* Vertical Ranked Rows with Hairline Dividers */}
              <div className="divide-y divide-white/[0.04]">
                {topAgents.map((ag, i) => {
                  const isPositive = ag.returnPct >= 0;
                  const isFirst = i === 0;
                  const cleanName = ag.name.replace(' (LLM)', '').replace('Baseline ', '');

                  return (
                    <div
                      key={ag.id}
                      className={cn(
                        'flex items-center justify-between py-2 transition-colors',
                        isFirst ? 'text-white' : 'text-zinc-300'
                      )}
                    >
                      {/* Left: Rank, Agent Name, Monochrome Outline Badge */}
                      <div className="flex items-center gap-2.5 min-w-0">
                        <span
                          className={cn(
                            'font-mono text-xs',
                            isFirst ? 'text-zinc-300 font-bold' : 'text-zinc-600'
                          )}
                        >
                          #{i + 1}
                        </span>
                        <span
                          className={cn(
                            'truncate font-sans',
                            isFirst ? 'text-sm font-semibold text-white' : 'text-xs text-zinc-300'
                          )}
                        >
                          {cleanName}
                        </span>
                        <CategoryBadge type={ag.id} />
                      </div>

                      {/* Right: Return value (only colored element in row) */}
                      <div
                        className={cn(
                          'font-mono font-bold tabular-nums text-right flex-shrink-0',
                          isFirst ? 'text-sm font-extrabold' : 'text-xs',
                          isPositive ? 'text-positive' : 'text-negative'
                        )}
                      >
                        {formatPct(ag.returnPct)}
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Docked Status Footer */}
              <div className="pt-2 border-t border-white/[0.06] flex items-center justify-between text-[10px] text-zinc-500">
                <span>Continuous Public Benchmark</span>
                <span className="text-zinc-400">EOD Cadence · NSE Close</span>
              </div>
            </div>

          </div>

        </div>
      </section>


      {/* =========================================================================
          SECTION 2 · THE EXPERIMENT PIPELINE (CONNECTED RAIL TIMELINE: ZERO BOXES)
          [No outer card, Stage 04 subtitle bounded, zero dangling lines]
          ========================================================================= */}
      <section className="pt-8 sm:pt-10 border-t border-border-hairline space-y-6">
        <SectionHeader title="The Experiment Pipeline" />

        {/* Connected Horizontal Timeline Rail */}
        <div className="relative pt-2 pb-2">
          <div className="hidden md:block absolute top-[16px] left-[5%] right-[5%] h-[1px] bg-white/10 z-0" />

          <div className="grid grid-cols-1 md:grid-cols-5 gap-8 md:gap-6 relative z-10">
            {EXPERIMENT_STAGES.map((st) => (
              <div key={st.step} className="space-y-3 font-mono text-xs">

                {/* Node on Rail */}
                <div className="flex items-center gap-3 md:block">
                  {st.isCore ? (
                    <div className="w-6 h-6 rounded-full bg-accent/20 border-2 border-accent flex items-center justify-center bg-[#121212] z-10 shadow-[0_0_12px_rgba(212,175,55,0.3)]">
                      <div className="w-2 h-2 rounded-full bg-accent animate-pulse" />
                    </div>
                  ) : (
                    <div className="w-4 h-4 rounded-full bg-[#181818] border border-zinc-600 z-10 my-1 flex items-center justify-center">
                      <div className="w-1 h-1 rounded-full bg-zinc-500" />
                    </div>
                  )}

                  <span className="md:hidden text-zinc-500 text-[10px] uppercase font-bold">
                    Stage {st.step}
                  </span>
                </div>

                {/* Typography below node */}
                <div className="space-y-1.5 pl-7 md:pl-0">
                  <div className="hidden md:flex items-center justify-between text-zinc-500 text-[10px]">
                    <span className="font-bold">STAGE {st.step}</span>
                  </div>

                  <h3
                    className={cn(
                      'font-sans text-sm font-medium',
                      st.isCore ? 'text-white font-semibold text-base' : 'text-zinc-200'
                    )}
                  >
                    {st.title}
                  </h3>

                  {st.subtitle && (
                    <div>
                      <span className="inline-block px-1.5 py-0.5 rounded text-[10px] font-mono text-accent bg-accent/10 border border-accent/20 uppercase tracking-wider">
                        {st.subtitle}
                      </span>
                    </div>
                  )}

                  <p className="text-xs sm:text-sm text-zinc-400 font-sans leading-relaxed pt-0.5">
                    {st.detail}
                  </p>
                </div>

              </div>
            ))}
          </div>

        </div>
      </section>


      {/* =========================================================================
          SECTION 3 · BUILT FOR RIGOR (FLAT COLUMNS: APPLE PRODUCT SPEC STYLE)
          [Zero container chrome, whitespace separated]
          ========================================================================= */}
      <section className="pt-8 sm:pt-10 border-t border-border-hairline space-y-6">
        <SectionHeader title="Built for Rigor" />

        {/* Flat Columns separated by whitespace */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-8 lg:gap-10">
          {TRUST_PILLARS.map((tp) => {
            const Icon = tp.icon;
            return (
              <div key={tp.title} className="space-y-2.5">
                <div className="flex items-center gap-2.5">
                  <Icon className="w-4 h-4 text-accent flex-shrink-0" />
                  <h3 className="font-sans font-medium text-white text-base">
                    {tp.title}
                  </h3>
                </div>
                <p className="text-sm text-zinc-400 font-sans leading-relaxed">
                  {tp.detail}
                </p>
              </div>
            );
          })}
        </div>
      </section>


      {/* =========================================================================
          SECTION 4 · THE CORE RESEARCH INQUIRIES
          [Dedicated Chapter Header, unconstrained text, clean hairline dividers, bottom-right links]
          ========================================================================= */}
      <section className="pt-8 sm:pt-10 border-t border-border-hairline space-y-8">
        <SectionHeader
          title="The Core Research Inquiries"
          subtitle="Empirical hypotheses evaluated under strict out-of-sample discipline"
        />

        {/* Question 01 */}
        <div className="space-y-4 pt-2">
          <h3 className="font-display text-2xl sm:text-3xl font-medium tracking-tight text-white">
            1. Can Autonomous Agent Personas Generate Real Equity Alpha?
          </h3>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 text-sm sm:text-base text-zinc-300 font-sans leading-relaxed">
            <div className="lg:col-span-6 space-y-3">
              <p>
                <strong className="text-white font-medium">Core Hypothesis:</strong> Testing whether autonomous LLM agents embodying distinct investment schools of thought can independently analyze market momentum, valuation filings, and corporate balance sheets to execute profitable trades without human intervention.
              </p>
            </div>
            <div className="lg:col-span-6 space-y-3">
              <p>
                <strong className="text-white font-medium">Evaluation Protocol:</strong> Rather than relying solely on realized portfolio returns, the trial evaluates selection alpha across all active recommendations, forward-return distributions on HOLD decisions, and prompt faithfulness audited against ground-truth market data.
              </p>
            </div>
          </div>

          {/* Bottom-Right Navigation Link */}
          <div className="pt-2 border-t border-white/[0.06] flex justify-end">
            <ActionLink to="/portfolio/simons" variant="primary">
              Inspect Persona Portfolios
            </ActionLink>
          </div>
        </div>

        {/* Question 02 */}
        <div className="space-y-4 pt-4 border-t border-white/[0.06]">
          <h3 className="font-display text-2xl sm:text-3xl font-medium tracking-tight text-white">
            2. Does Heavy Inference Outperform Matched Rules?
          </h3>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 text-sm sm:text-base text-zinc-300 font-sans leading-relaxed">
            <div className="lg:col-span-6 space-y-3">
              <p>
                <strong className="text-white font-medium">Core Hypothesis:</strong> Evaluating whether the significant computational overhead, token expenditure, and execution latency of an LLM decision layer produce demonstrable excess return over identical, deterministic Python rules executing on the exact same market bars.
              </p>
            </div>
            <div className="lg:col-span-6 space-y-3">
              <p>
                <strong className="text-white font-medium">Evaluation Protocol:</strong> Every LLM agent is paired symmetrically against a rules control executing through the identical simulated broker with identical starting capital (₹5,00,000 per agent) and identical statutory charges, isolating reasoning value from market drift.
              </p>
            </div>
          </div>

          {/* Bottom-Right Navigation Link */}
          <div className="pt-2 border-t border-white/[0.06] flex justify-end">
            <ActionLink to="/comparison" variant="primary">
              Compare 5 Matched Pairs in Detail
            </ActionLink>
          </div>
        </div>

      </section>


      {/* =========================================================================
          SECTION 5 · THE FIVE OBSERVED PERSONAS (EDITORIAL DIRECTORY: NO CARDS)
          [Zero formulaic rule hurdles, calibrated text lengths, bottom-baseline alignment]
          ========================================================================= */}
      <section className="pt-8 sm:pt-10 border-t border-border-hairline space-y-6">
        <SectionHeader title="The Five Observed Personas" />

        {/* 5-Column Typographic Directory with Uniform Height and Bottom Baseline Alignment */}
        <div className="grid grid-cols-1 md:grid-cols-5 gap-0 font-sans">
          {SCHOOLS_OF_THOUGHT.map((phi) => (
            <div
              key={phi.personaId}
              className="flex flex-col justify-between h-full border-b md:border-b-0 md:border-r border-border-hairline last:border-r-0 py-6 md:py-0 md:px-4 lg:px-5 first:pl-0 last:pr-0"
            >
              <div className="space-y-3">
                <div className="flex items-center justify-between text-xs font-mono text-zinc-500">
                  <span className="font-bold">{phi.index}</span>
                  <span>{phi.horizon}</span>
                </div>

                <div>
                  <h3 className="font-display text-lg font-medium text-white">
                    {phi.name}
                  </h3>
                  <div className="text-xs text-zinc-400 mt-0.5">
                    Inspired by {phi.inspiration}
                  </div>
                </div>

                <div className="text-xs font-mono text-accent min-h-[32px] flex items-center">
                  {phi.mandate}
                </div>

                <p className="text-xs sm:text-sm text-zinc-400 font-sans leading-relaxed">
                  {phi.profile}
                </p>
              </div>

              <div className="pt-4 mt-auto">
                <ActionLink to={`/portfolio/${phi.personaId}`} variant="subdued">
                  Portfolio & Dossier
                </ActionLink>
              </div>
            </div>
          ))}
        </div>

        {/* Bottom-Right Navigation Link */}
        <div className="flex justify-end pt-3 border-t border-white/[0.06]">
          <ActionLink to="/comparison" variant="primary">
            Compare All 5 Schools of Thought
          </ActionLink>
        </div>
      </section>


      {/* =========================================================================
          SECTION 6 · LIVE ACTIVITY FEED (MINIMALIST TERMINAL LOG STREAM)
          [Clean divided rows without box, bottom-right link]
          ========================================================================= */}
      <section className="pt-8 sm:pt-10 border-t border-border-hairline space-y-6">
        <SectionHeader title="Latest Live Activity" />

        {/* Minimalist Log Stream */}
        <div className="divide-y divide-white/[0.06] border-y border-border-hairline font-mono text-xs">
          {recentEvents.length === 0 ? (
            <div className="py-6 text-center text-zinc-500">
              No recent execution events recorded today.
            </div>
          ) : (
            recentEvents.map((evt) => (
              <div
                key={evt.id}
                className="py-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-2 hover:bg-white/[0.02] transition-colors"
              >
                <div className="flex items-center gap-3">
                  <span
                    className={cn(
                      'px-1.5 py-0.5 rounded text-[10px] font-semibold tracking-wider border',
                      evt.eventType.includes('FILL')
                        ? 'border-emerald-500/30 text-emerald-400 bg-emerald-500/10'
                        : evt.eventType.includes('EXPIRED')
                          ? 'border-zinc-500/30 text-zinc-400 bg-white/[0.02]'
                          : 'border-accent/30 text-accent bg-accent/10'
                    )}
                  >
                    {evt.eventType}
                  </span>
                  <span className="font-bold text-white">
                    {(evt.agentId || 'SYSTEM').replace('baseline-', '').toUpperCase()}
                  </span>
                  {evt.symbol && (
                    <span className="px-1.5 py-0.2 rounded bg-white/[0.04] text-zinc-300 border border-white/5 font-sans">
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

        {/* Bottom-Right Navigation Link */}
        <div className="flex justify-end pt-1">
          <ActionLink to="/pulse" variant="primary">
            Full Activity Ledger
          </ActionLink>
        </div>
      </section>


      {/* =========================================================================
          SECTION 7 · CLOSING VERDICT & PROTOCOL STANDING
          [Editorial callout with left accent bar, generous whitespace]
          ========================================================================= */}
      <section className="pt-8 sm:pt-10 border-t border-border-hairline">
        <div className="border-l-2 border-accent pl-6 sm:pl-8 space-y-4 font-sans">
          <h3 className="font-display text-2xl sm:text-3xl font-medium text-white tracking-tight leading-tight">
            The empirical observation trial is actively underway.
          </h3>

          <p className="text-sm sm:text-base text-zinc-300 leading-relaxed max-w-4xl">
            Statistical conclusions require a rigorous threshold of approximately 30 closed round-trip trades per agent across contrasting market regimes. While initial pilot mark-to-market positions are live, we do not declare premature alpha superiority. Daily order execution, prompt adherence, and thesis forensics remain continuously audited and open for inspection.
          </p>

          <div className="pt-3 flex flex-wrap items-center gap-6 text-sm font-sans font-medium">
            <ActionLink to="/leaderboard" variant="primary">
              Full Leaderboard Standings
            </ActionLink>

            <ActionLink to="/comparison" variant="secondary">
              Inspect Head-to-Head Duels
            </ActionLink>

            <ActionLink to="/pulse" variant="secondary">
              System Telemetry & Health
            </ActionLink>
          </div>
        </div>
      </section>

    </div>
  );
}
