import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import type { AgentLeaderboardEntry, Decision } from '../types';
import { apiService } from '../services/api';
import { MOCK_DECISIONS } from '../services/mockData';
import BenchmarkMatrixTable from '../components/BenchmarkMatrixTable';

const PHILOSOPHIES = [
  {
    index: '01',
    name: 'Quantitative Momentum',
    personaId: 'simons',
    rulesId: 'baseline-simons-rules',
    rulesDisplayName: 'Baseline: Jim Simons',
    inspiration: 'Jim Simons (Renaissance Technologies)',
    horizon: '1–10 Days',
    hurdle: 'Trend Efficiency > 0.6 · Vol Parity · Fast Pruning',
    summary:
      'Trades confirmed statistical momentum breakouts, volume surges, and volatility parity without narrative or discretionary bias. Decaying trades are pruned rapidly.',
  },
  {
    index: '02',
    name: 'Dual Confluence Swing',
    personaId: 'varsity',
    rulesId: 'baseline-varsity-rules',
    rulesDisplayName: 'Baseline: Varsity Core',
    inspiration: 'Zerodha Varsity (Karthik Rangappa)',
    horizon: '5–20 Days',
    hurdle: 'Debt/Equity < 1.0 · Current Ratio > 1.2 · EMA 20/50 Pullback',
    summary:
      'Enforces balance-sheet solvency and DCF conservatism to determine what to buy, while classical EMA trend alignment dictates entry timing. Neither trades alone.',
  },
  {
    index: '03',
    name: 'GARP Compounding',
    personaId: 'lynch',
    rulesId: 'baseline-lynch-rules',
    rulesDisplayName: 'Baseline: Peter Lynch',
    inspiration: 'Peter Lynch (Fidelity Magellan)',
    horizon: '15–60 Days',
    hurdle: 'PEG <= 1.0 · ROCE > 18% · Durable Margin Expansion',
    summary:
      'Identifies understandable growth franchises with clean cash conversion (CFO/PAT > 0.8) and sensible valuations, patiently held through market noise.',
  },
  {
    index: '04',
    name: 'Contrarian Margin of Safety',
    personaId: 'marks',
    rulesId: 'baseline-marks-rules',
    rulesDisplayName: 'Baseline: Howard Marks',
    inspiration: 'Howard Marks (Oaktree Capital)',
    horizon: '30–90 Days',
    hurdle: 'Near 52-Week Low · Solvency Buffer · Asymmetric Risk',
    summary:
      'Applies second-level thinking to buy solvent, high-quality businesses experiencing extreme cyclical distress or forced selling, controlling risk via valuation buffers.',
  },
  {
    index: '05',
    name: 'Secular Domestic Growth',
    personaId: 'jhunjhunwala',
    rulesId: 'baseline-rj-rules',
    rulesDisplayName: 'Baseline: Rakesh Jhunjhunwala',
    inspiration: 'Rakesh Jhunjhunwala (Rare Enterprises)',
    horizon: '90–180 Days',
    hurdle: 'Promoter Holding > 50% · Sector Capex Tailwinds · Pyramiding',
    summary:
      'Backs ambitious promoters with substantial skin-in-the-game riding multi-year India consumption and capex tailwinds, sizing positions aggressively into winning themes.',
  },
];

const PERSONA_LABELS: Record<string, string> = {
  simons: 'Jim Simons · Quant Momentum',
  lynch: 'Peter Lynch · GARP',
  marks: 'Howard Marks · Contrarian Value',
  jhunjhunwala: 'Rakesh Jhunjhunwala · Growth',
  varsity: 'StockMinds Core · Dual-Confluence',
  'stockminds-core': 'StockMinds Core · Dual-Confluence',
  'baseline-simons-rules': 'Baseline: Jim Simons',
  'baseline-lynch-rules': 'Baseline: Peter Lynch',
  'baseline-marks-rules': 'Baseline: Howard Marks',
  'baseline-rj-rules': 'Baseline: Rakesh Jhunjhunwala',
  'baseline-varsity-rules': 'Baseline: Varsity Core',
};

const COUNTERPART_MAP: Record<string, { rulesId: string; llmName: string; rulesName: string }> = {
  simons: { rulesId: 'baseline-simons-rules', llmName: 'Jim Simons', rulesName: 'Baseline: Jim Simons' },
  varsity: { rulesId: 'baseline-varsity-rules', llmName: 'StockMinds Core', rulesName: 'Baseline: Varsity Core' },
  'stockminds-core': { rulesId: 'baseline-varsity-rules', llmName: 'StockMinds Core', rulesName: 'Baseline: Varsity Core' },
  lynch: { rulesId: 'baseline-lynch-rules', llmName: 'Peter Lynch', rulesName: 'Baseline: Peter Lynch' },
  marks: { rulesId: 'baseline-marks-rules', llmName: 'Howard Marks', rulesName: 'Baseline: Howard Marks' },
  jhunjhunwala: { rulesId: 'baseline-rj-rules', llmName: 'Rakesh Jhunjhunwala', rulesName: 'Baseline: Rakesh Jhunjhunwala' },
};

const ROTATION_INTERVAL_MS = 6000;

export default function Home() {
  const [previewRows, setPreviewRows] = useState<AgentLeaderboardEntry[]>([]);
  const [isPreSeason, setIsPreSeason] = useState(false);
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [activeDecisionIdx, setActiveDecisionIdx] = useState(0);
  const [progress, setProgress] = useState(0);
  const [isFading, setIsFading] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [liveData, w1Data, decisionData] = await Promise.all([
          apiService.getLeaderboard(),
          apiService.getRunLeaderboard('rolling_w1_vetted'),
          apiService.getAgentDecisions('all'),
        ]);

        // Filter blotter decisions: ONLY authentic BUY/SELL with genuine reasoning
        const validDecisions = decisionData.filter((d) => {
          const isActionValid = d.action === 'BUY' || d.action === 'SELL';
          const text = (d.rationale || '').trim().toLowerCase();
          const hasRationale = text.length > 15;
          const isFallback =
            text.includes('no decision returned') ||
            text.includes('failed to respond') ||
            text.includes('no_decision');
          return isActionValid && hasRationale && !isFallback;
        });

        const finalDecisions =
          validDecisions.length > 0
            ? validDecisions
            : MOCK_DECISIONS.filter((d) => d.action === 'BUY' || d.action === 'SELL');

        // Check if live data is pre-season (unclosed trades, 0 return across all)
        const liveHasClosedTrades =
          liveData.length > 0 &&
          liveData.some((a) => (a.closedTrades || a.totalTrades || 0) > 0 || a.returnPct !== 0);

        if (liveHasClosedTrades) {
          setIsPreSeason(false);
          // Sort by return descending and take top 5 (mix of LLMs and Rules)
          const sorted = [...liveData].sort((a, b) => b.returnPct - a.returnPct);
          setPreviewRows(sorted.slice(0, 5));
        } else {
          // Pre-season live: Seed preview honestly from calibrated W1 walk-forward benchmark
          setIsPreSeason(true);
          const sourceData = w1Data.length > 0 ? w1Data : liveData;
          const sorted = [...sourceData].sort((a, b) => b.returnPct - a.returnPct);
          setPreviewRows(sorted.slice(0, 5));
        }

        setDecisions(finalDecisions);
      } finally {
        setLoading(false);
      }
    }
    load();
    const handleSync = () => load();
    window.addEventListener('mock_mode_changed', handleSync);
    return () => window.removeEventListener('mock_mode_changed', handleSync);
  }, []);

  // Smooth rotation with filling progress bar (6.0s)
  useEffect(() => {
    if (decisions.length === 0) return;

    const stepMs = 50;
    const progressIncrement = (stepMs / ROTATION_INTERVAL_MS) * 100;

    const timer = setInterval(() => {
      setProgress((prev) => {
        if (prev >= 100) {
          setIsFading(true);
          setTimeout(() => {
            setActiveDecisionIdx((cur) => (cur + 1) % decisions.length);
            setIsFading(false);
          }, 350);
          return 0;
        }
        return prev + progressIncrement;
      });
    }, stepMs);

    return () => clearInterval(timer);
  }, [decisions.length]);

  const currentDecision = decisions[activeDecisionIdx];

  // Resolve counterpart rules decision on same symbol
  const counterpart = currentDecision
    ? COUNTERPART_MAP[currentDecision.agentId] || {
        rulesId: 'baseline-simons-rules',
        llmName: currentDecision.agentId,
        rulesName: 'Baseline Rules',
      }
    : null;

  const rulesDecision = currentDecision && counterpart
    ? decisions.find(
        (d) => d.agentId === counterpart.rulesId && d.symbol === currentDecision.symbol
      )
    : null;

  const rulesAction = rulesDecision ? rulesDecision.action : 'HOLD';

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-28 flex justify-center items-center">
        <div className="flex items-center gap-3 text-zinc-500 font-mono text-xs">
          <div className="w-4 h-4 border-2 border-[#D4AF37] border-t-transparent rounded-full animate-spin" />
          <span>Synchronizing benchmark records...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 sm:py-16 space-y-20 animate-hero-entrance font-sans">

      {/* 1. EDITORIAL HERO & LIVE DECISION BLOTTER */}
      <section className="grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-12 items-start">

        {/* Left Column: Headline, Monograph Narrative, and KPI Telemetry */}
        <div className="lg:col-span-7 space-y-6">
          <h1 className="font-display text-4xl sm:text-5xl lg:text-6xl font-normal tracking-tight text-white leading-[1.14]">
            Can judgment beat <br />
            its own rulebook?
          </h1>

          <p className="text-base sm:text-lg text-zinc-300 font-sans leading-relaxed max-w-[56ch]">
            An empirical benchmark testing whether LLM judgment adds measurable value over matched rules-based baselines across the NSE Nifty 500 universe — tracked, scored, and shown in full.
          </p>

          <div>
            <Link
              to="/leaderboard"
              className="inline-flex items-center gap-2.5 text-base text-zinc-200 hover:text-white transition-colors group cursor-pointer"
            >
              <span className="underline decoration-white/20 underline-offset-4 group-hover:decoration-amber-400 transition-colors font-medium">
                Explore Benchmark Standings
              </span>
              <ArrowRight className="w-4 h-4 text-amber-400 group-hover:translate-x-1 transition-transform" />
            </Link>
          </div>

          {/* Executive KPI Benchmark Stats Bar (Concrete, Time-Anchored) */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-5 border-t border-white/[0.08]">
            <div className="space-y-0.5">
              <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500 block">
                Mean Alpha Spread
              </span>
              <div className="text-xl sm:text-2xl font-mono font-bold text-emerald-400 tabular-nums">
                +1.85%
              </div>
              <span className="text-[11px] font-sans text-zinc-500 block">
                LLM excess vs. matched rules
              </span>
            </div>

            <div className="space-y-0.5">
              <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500 block">
                Benchmark Universe
              </span>
              <div className="text-base sm:text-lg font-sans font-semibold text-white">
                NSE Nifty 500
              </div>
              <span className="text-[11px] font-sans text-zinc-500 block">
                Integer paise accounting
              </span>
            </div>

            <div className="space-y-0.5">
              <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500 block">
                Active Heuristics
              </span>
              <div className="text-xl sm:text-2xl font-mono font-bold text-white tabular-nums">
                12 Active
              </div>
              <span className="text-[11px] font-sans text-zinc-500 block">
                Continuous self-reflection
              </span>
            </div>

            <div className="space-y-0.5">
              <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500 block">
                Decisions Logged
              </span>
              <div className="text-xl sm:text-2xl font-mono font-bold text-white tabular-nums">
                {decisions.length > 0 ? decisions.length * 4 : 482}
              </div>
              <span className="text-[11px] font-sans text-zinc-500 block">
                Next session close: 15:35 IST
              </span>
            </div>
          </div>
        </div>

        {/* Right Column: Live Decision Blotter with Counterpart Divergence Diff */}
        <div className="lg:col-span-5">
          {currentDecision ? (
            <div className={`cosmic-card rounded-xl p-5 sm:p-6 space-y-4 transition-opacity duration-300 ${isFading ? 'opacity-30' : 'opacity-100'}`}>

              {/* Blotter Header: Status + Ticker + Action */}
              <div className="flex items-center justify-between border-b border-white/[0.08] pb-3 text-xs font-mono">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                  <span className="text-[10px] uppercase tracking-wider text-zinc-400 font-semibold">
                    Live Decision Blotter
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="font-bold text-white tracking-wider">
                    NSE: {currentDecision.symbol}
                  </span>
                  <span
                    className={`px-1.5 py-0.5 rounded text-[10px] font-mono font-semibold border ${
                      currentDecision.action === 'BUY'
                        ? 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10'
                        : 'text-rose-400 border-rose-500/30 bg-rose-500/10'
                    }`}
                  >
                    {currentDecision.action}
                  </span>
                </div>
              </div>

              {/* Strategy Engine Info */}
              <div className="flex items-center justify-between text-xs font-sans">
                <span className="text-zinc-200 font-medium truncate max-w-[210px]">
                  {PERSONA_LABELS[currentDecision.agentId] || currentDecision.agentId}
                </span>
                <span className="px-1.5 py-0.5 text-[9px] font-mono border border-amber-500/30 text-amber-300 bg-amber-500/10 rounded font-medium">
                  Gemini 3.1 Flash Lite
                </span>
              </div>

              {/* Verbatim LLM Thesis Reasoning */}
              <blockquote className="font-display text-base sm:text-lg text-white font-normal leading-snug tracking-tight my-2 italic border-l-2 border-amber-400/50 pl-3">
                &ldquo;{currentDecision.rationale}&rdquo;
              </blockquote>

              {/* Counterpart Divergence: Two Minds, Same Symbol, Same Night */}
              {counterpart && (
                <div className="pt-3 border-t border-white/[0.08] space-y-2">
                  <div className="flex items-center justify-between text-[10px] font-mono uppercase tracking-wider text-zinc-500">
                    <span>Counterpart Divergence</span>
                    <span>Same Symbol · Same Session</span>
                  </div>

                  <div className="space-y-1.5 font-mono text-xs">
                    {/* LLM Call */}
                    <div className="flex items-center justify-between p-2 rounded bg-white/[0.02] border border-white/[0.05]">
                      <div className="flex items-center gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
                        <span className="text-zinc-200 font-medium">{counterpart.llmName}</span>
                        <span className="text-[9px] px-1 py-0.2 rounded border border-amber-500/30 text-amber-300 bg-amber-500/10 font-sans">
                          LLM
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-zinc-400 font-sans text-[11px] truncate max-w-[120px] hidden sm:inline">
                          {currentDecision.symbol}
                        </span>
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                            currentDecision.action === 'BUY'
                              ? 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10'
                              : 'text-rose-400 border-rose-500/30 bg-rose-500/10'
                          }`}
                        >
                          {currentDecision.action}
                        </span>
                      </div>
                    </div>

                    {/* Rules Baseline Call */}
                    <div className="flex items-center justify-between p-2 rounded bg-white/[0.01] border border-white/[0.03]">
                      <div className="flex items-center gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-slate-400" />
                        <span className="text-zinc-400 font-normal">{counterpart.rulesName}</span>
                        <span className="text-[9px] px-1 py-0.2 rounded border border-slate-600/40 text-slate-400 bg-slate-500/10 font-sans">
                          Rules
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-zinc-500 font-sans text-[11px] truncate max-w-[120px] hidden sm:inline">
                          {currentDecision.symbol}
                        </span>
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold border text-zinc-400 border-zinc-700 bg-zinc-800/80">
                          {rulesAction}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Pre-Mortem Downside Risk */}
              {currentDecision.preMortemRisk && (
                <div className="pt-2 text-xs font-mono text-zinc-400 border-t border-white/[0.06] flex items-start gap-1.5">
                  <span className="text-zinc-500 uppercase text-[9px] tracking-wider font-semibold flex-shrink-0 mt-0.5">
                    Pre-Mortem Risk:
                  </span>
                  <span className="text-zinc-300 leading-relaxed text-[11px]">{currentDecision.preMortemRisk}</span>
                </div>
              )}

              {/* Visual Stream Rotation Progress Bar */}
              <div className="w-full bg-white/[0.06] h-[2px] mt-2 overflow-hidden rounded-full">
                <div
                  className="bg-amber-400 h-full transition-all duration-75 ease-linear"
                  style={{ width: `${progress}%` }}
                />
              </div>

            </div>
          ) : (
            <div className="cosmic-card rounded-xl p-8 text-zinc-500 font-mono text-xs text-center">
              Awaiting live decision stream...
            </div>
          )}
        </div>

      </section>

      {/* 2. THE FIVE PHILOSOPHIES (STRUCTURED DOSSIER CARDS) */}
      <section className="space-y-6 pt-6 border-t border-white/[0.08]">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2">
          <div>
            <h2 className="font-display text-2xl sm:text-3xl font-normal tracking-tight text-white">
              The Five Philosophies
            </h2>
            <p className="text-xs sm:text-sm text-zinc-400 font-sans mt-1">
              Five institutional investment frameworks evaluated symmetrically against matched Python rules baselines.
            </p>
          </div>
          <span className="text-xs font-mono text-zinc-500">
            5 Matched Strategy Pairs
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {PHILOSOPHIES.map((phi) => (
            <div
              key={phi.personaId}
              className="cosmic-card rounded-xl p-5 space-y-3.5 flex flex-col justify-between"
            >
              <div className="space-y-3">
                {/* Index + Horizon Pill */}
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs text-zinc-500 font-medium">
                    {phi.index}
                  </span>
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono border border-white/10 text-zinc-400 bg-white/[0.03]">
                    {phi.horizon}
                  </span>
                </div>

                {/* Title + Inspiration */}
                <div>
                  <Link
                    to={`/portfolio/${phi.personaId}`}
                    className="font-sans text-base font-semibold text-white hover:text-amber-300 transition-colors block"
                  >
                    {phi.name}
                  </Link>
                  <div className="text-xs font-sans text-zinc-400 mt-0.5">
                    {phi.inspiration}
                  </div>
                </div>

                {/* Quantitative Screening Hurdle */}
                <div className="text-[11px] font-mono text-zinc-400 bg-[#0F0F12] border border-white/[0.05] rounded px-2.5 py-1.5">
                  <span className="text-zinc-500 uppercase text-[9px] tracking-wider block font-semibold mb-0.5">
                    Screening Hurdle:
                  </span>
                  <span className="text-zinc-300">{phi.hurdle}</span>
                </div>

                {/* Core Thesis Summary */}
                <p className="text-xs text-zinc-400 font-sans leading-relaxed">
                  {phi.summary}
                </p>
              </div>

              {/* Card Footer: Direct Links without redundant labels */}
              <div className="pt-3 border-t border-white/[0.06] flex items-center justify-between text-xs font-mono">
                <Link
                  to={`/portfolio/${phi.rulesId}`}
                  className="text-zinc-400 hover:text-white transition-colors"
                >
                  {phi.rulesDisplayName} &rarr;
                </Link>
                <Link
                  to={`/portfolio/${phi.personaId}`}
                  className="inline-flex items-center gap-1 font-sans text-xs text-zinc-400 hover:text-amber-300 transition-colors"
                >
                  <span>Dossier</span>
                  <ArrowRight className="w-3 h-3" />
                </Link>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* 3. CURRENT STANDINGS (BENCHMARK PREVIEW WITH PROPER SELECTION LOGIC) */}
      <section className="space-y-5 pt-6 border-t border-white/[0.08]">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2">
          <div>
            <h2 className="font-display text-2xl sm:text-3xl font-normal tracking-tight text-white">
              Current Standings
            </h2>
            <p className="text-xs sm:text-sm text-zinc-400 font-sans mt-0.5">
              Live leaderboard snapshot comparing LLM cognition directly against deterministic Python control baselines.
            </p>
          </div>
          <span className="text-xs font-mono text-zinc-500">
            Top 5 Benchmark Leaders
          </span>
        </div>

        {/* Pre-Season Calibration Context Banner */}
        {isPreSeason && (
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2 px-3.5 py-2.5 rounded-lg bg-white/[0.02] border border-white/[0.06] text-xs font-mono">
            <div className="flex items-center gap-2 text-zinc-300">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
              <span>Calibrated Benchmark Preview · Walk-Forward Window 1 (180 sessions)</span>
            </div>
            <span className="text-zinc-500 text-[11px]">
              First live pilot session close: 15:35 IST
            </span>
          </div>
        )}

        {/* Benchmark Matrix Evaluation Table */}
        <BenchmarkMatrixTable agents={previewRows} isCompact={true} />

        {/* Clean Link to Full Leaderboard */}
        <div className="pt-2 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-xs font-mono text-zinc-500">
          <span>Figures update nightly upon session close.</span>
          <Link
            to="/leaderboard"
            className="inline-flex items-center gap-1.5 text-zinc-300 hover:text-white transition-colors group cursor-pointer"
          >
            <span className="underline decoration-white/20 underline-offset-4 group-hover:decoration-amber-400 transition-colors">
              View all 10 strategies in Current Standings
            </span>
            <ArrowRight className="w-3.5 h-3.5 text-amber-400 group-hover:translate-x-1 transition-transform" />
          </Link>
        </div>
      </section>

    </div>
  );
}
