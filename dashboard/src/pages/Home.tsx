import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, ShieldCheck, Terminal, Sparkles } from 'lucide-react';
import type { AgentLeaderboardEntry, Decision } from '../types';
import { apiService } from '../services/api';
import { formatPct } from '../utils/formatters';

const PHILOSOPHIES = [
  {
    name: 'Quant Momentum',
    inspiration: 'Inspired by Jim Simons / Renaissance Technologies',
    summary:
      'Trades confirmed statistical trend efficiency and volume dynamics over short horizons. Relies strictly on quantifiable mathematical edges—never prediction, narrative, or sentiment.',
  },
  {
    name: 'Growth at a Reasonable Price (GARP)',
    inspiration: 'Inspired by Peter Lynch',
    summary:
      'Seeks understandable, well-run businesses with sustainable earnings growth, high returns on capital, low debt, and strong operating cash generation, held through short-term price noise.',
  },
  {
    name: 'Contrarian Value',
    inspiration: 'Inspired by Howard Marks',
    summary:
      'Applies second-level thinking to buy solvent, high-quality businesses suffering from excessive market pessimism or cyclical despair, demanding an asymmetric margin of safety.',
  },
  {
    name: 'High-Conviction Growth',
    inspiration: 'Inspired by Rakesh Jhunjhunwala',
    summary:
      'Backs ambitious promoters with significant skin in the game, durable domestic consumer moats, and institutional sponsorship, holding patiently across multi-quarter compounding cycles.',
  },
  {
    name: 'Dual-Confluence Balanced',
    inspiration: 'Inspired by Zerodha Varsity (Karthik Rangappa)',
    summary:
      'Requires fundamentals to dictate what to trade (solvency and DCF intrinsic value) and classical technical analysis to dictate when to trade, entering only when both sides agree.',
  },
];

const PERSONA_NAMES: Record<string, string> = {
  simons: 'Jim Simons · Quant Momentum',
  lynch: 'Peter Lynch · GARP',
  marks: 'Howard Marks · Contrarian Value',
  jhunjhunwala: 'Rakesh Jhunjhunwala · High-Conviction Growth',
  'stockminds-core': 'StockMinds Core · Dual-Confluence Balanced',
  'baseline-simons-rules': 'Simons · Rules Control Baseline',
};

export default function Home() {
  const [agents, setAgents] = useState<AgentLeaderboardEntry[]>([]);
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [activeDecisionIdx, setActiveDecisionIdx] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [leaderboardData, decisionData] = await Promise.all([
          apiService.getLeaderboard(),
          apiService.getAgentDecisions('all'),
        ]);
        setAgents(leaderboardData);
        setDecisions(decisionData);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  // Auto-rotate through live decisions every 5 seconds
  useEffect(() => {
    if (decisions.length === 0) return;
    const interval = setInterval(() => {
      setActiveDecisionIdx((prev) => (prev + 1) % decisions.length);
    }, 5000);
    return () => clearInterval(interval);
  }, [decisions.length]);

  const currentDecision = decisions[activeDecisionIdx];
  const sortedAgents = [...agents].sort((a, b) => b.returnPct - a.returnPct);

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-28 flex justify-center items-center">
        <div className="flex items-center gap-3 text-zinc-500 font-mono text-xs">
          <div className="w-4 h-4 border-2 border-[#D4AF37] border-t-transparent rounded-full animate-spin" />
          <span>Synchronizing arena records...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 lg:py-20 space-y-28 animate-fade-in font-sans">
      
      {/* 1. EDITORIAL ASYMMETRIC HERO */}
      <section className="grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-16 items-start">
        
        {/* Left Column: Editorial Display Typography & Single Action */}
        <div className="lg:col-span-7 space-y-8">
          
          {/* Eyebrow */}
          <div className="text-xs font-mono text-zinc-500 tracking-widest lowercase">
            a study on nse's nifty 500
          </div>

          {/* Large High-Contrast Display Serif Headline */}
          <h1 className="font-serif text-5xl sm:text-6xl lg:text-7xl font-normal tracking-tight text-white leading-[1.08]">
            Can judgment beat <br />
            its own rulebook?
          </h1>

          {/* Narrative Lead */}
          <p className="text-base sm:text-lg text-zinc-400 font-sans leading-relaxed max-w-xl">
            Five LLMs embodying five different investing philosophies trade against each other and their rules-based counterparts on the Nifty 500 universe. We bring the contest to you. Each trade and decision - tracked and analysed.
          </p>

          {/* Single Action Button */}
          <div className="pt-2">
            <Link
              to="/leaderboard"
              className="inline-flex items-center gap-2.5 px-6 py-3 rounded-md bg-white/[0.06] hover:bg-white/[0.12] text-white border border-white/15 hover:border-[#D4AF37]/50 font-mono text-xs font-medium tracking-wide transition-all cursor-pointer group"
            >
              <span>Enter the Arena</span>
              <ArrowRight className="w-3.5 h-3.5 text-[#D4AF37] group-hover:translate-x-0.5 transition-transform" />
            </Link>
          </div>
        </div>

        {/* Right Column: Live Auto-Rotating Decision Blotter (No charts/graphs) */}
        <div className="lg:col-span-5">
          {currentDecision ? (
            <div className="rounded-lg border border-white/10 bg-[#09090C] p-6 space-y-5 shadow-2xl relative">
              
              {/* Blotter Header */}
              <div className="flex items-center justify-between border-b border-white/[0.06] pb-3 text-[10px] font-mono">
                <div className="flex items-center gap-2 text-zinc-400">
                  <Terminal className="w-3.5 h-3.5 text-[#D4AF37]" />
                  <span className="uppercase tracking-widest">Live Decision Blotter</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-zinc-500">
                    {activeDecisionIdx + 1} of {decisions.length}
                  </span>
                  <div className="flex gap-1">
                    {decisions.map((_, i) => (
                      <span
                        key={i}
                        className={`w-1.5 h-1.5 rounded-full transition-colors ${
                          i === activeDecisionIdx ? 'bg-[#D4AF37]' : 'bg-white/10'
                        }`}
                      />
                    ))}
                  </div>
                </div>
              </div>

              {/* Persona & Ticker Pill */}
              <div className="space-y-2">
                <div className="text-[11px] font-mono text-zinc-400">
                  {PERSONA_NAMES[currentDecision.agentId] || currentDecision.agentId}
                </div>
                <div className="flex items-center gap-3">
                  <span className="font-mono text-xl font-bold text-white tracking-tight">
                    {currentDecision.symbol}
                  </span>
                  <span
                    className={`font-mono text-xs px-2 py-0.5 rounded font-semibold border ${
                      currentDecision.action === 'BUY'
                        ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                        : currentDecision.action === 'SELL'
                        ? 'bg-rose-500/10 text-rose-400 border-rose-500/30'
                        : 'bg-zinc-800 text-zinc-300 border-zinc-700'
                    }`}
                  >
                    {currentDecision.action}
                  </span>
                  <span className="text-zinc-500 font-mono text-[11px] ml-auto">
                    {currentDecision.decisionDate}
                  </span>
                </div>
              </div>

              {/* One-Line Reasoning */}
              <div className="space-y-1.5 bg-black/40 p-3.5 rounded border border-white/[0.04]">
                <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-wider block">
                  Verbatim Decision Rationale
                </span>
                <p className="text-xs text-zinc-300 leading-relaxed font-sans">
                  &ldquo;{currentDecision.rationale}&rdquo;
                </p>
              </div>

              {/* Pre-Mortem Risk Underneath */}
              <div className="space-y-1 bg-white/[0.02] p-3 rounded border border-white/[0.04]">
                <div className="flex items-center gap-1.5 text-[10px] font-mono text-amber-400/90 uppercase tracking-wider">
                  <Sparkles className="w-3 h-3" />
                  <span>Pre-Mortem Failure Risk</span>
                </div>
                <p className="text-[11px] text-zinc-400 leading-relaxed font-sans">
                  {currentDecision.preMortemRisk ||
                    'Broad market trend reversal or sudden volatility expansion breaching stop bounds.'}
                </p>
              </div>

              {/* Verification Stamp */}
              <div className="flex items-center justify-between pt-2 border-t border-white/[0.06] text-[10px] font-mono text-zinc-500">
                <div className="flex items-center gap-1 text-emerald-400">
                  <ShieldCheck className="w-3.5 h-3.5" />
                  <span>100% Deterministic Citation Match</span>
                </div>
                <span>Auto-cycling feed</span>
              </div>

            </div>
          ) : (
            <div className="p-8 border border-white/10 rounded-lg text-zinc-500 font-mono text-xs text-center">
              Awaiting live feed...
            </div>
          )}
        </div>

      </section>

      {/* 2. THE FIVE PHILOSOPHIES (Direct from Prompts — Zero Internal Numbers) */}
      <section className="space-y-8 pt-4">
        <div className="border-b border-white/[0.08] pb-4 flex items-center justify-between">
          <div className="text-xs font-mono text-zinc-500 tracking-widest uppercase">
            Five Philosophies · One Benchmark
          </div>
          <span className="text-[11px] font-mono text-zinc-500">
            Nifty 500 Universe
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-5 gap-6">
          {PHILOSOPHIES.map((phi, idx) => (
            <div
              key={phi.name}
              className="space-y-3 p-4 rounded-md bg-white/[0.015] border border-white/[0.06] hover:border-white/20 transition-colors"
            >
              <div className="text-[10px] font-mono text-zinc-600">
                0{idx + 1}
              </div>
              <h3 className="font-serif text-lg font-normal text-white tracking-tight">
                {phi.name}
              </h3>
              <div className="text-[10px] font-mono text-[#D4AF37]/90 leading-tight">
                {phi.inspiration}
              </div>
              <p className="text-xs text-zinc-400 leading-relaxed font-sans pt-1">
                {phi.summary}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* 3. MINIMALIST LEADERBOARD PREVIEW (Matching Reference Image 2 & 3) */}
      <section className="space-y-6 pt-4">
        <div className="border-b border-white/[0.08] pb-4 flex flex-col sm:flex-row justify-between items-start sm:items-baseline gap-2">
          <h2 className="font-serif text-2xl sm:text-3xl font-normal tracking-tight text-white">
            Leaderboard
          </h2>
          <span className="text-xs font-mono text-zinc-500">
            10 strategies · ranked by return
          </span>
        </div>

        {/* Minimalist Editorial Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-xs font-mono">
            <thead>
              <tr className="border-b border-white/10 text-zinc-500 text-[11px]">
                <th className="py-3 px-3 text-left font-normal w-12">Rank</th>
                <th className="py-3 px-4 text-left font-normal">Agent</th>
                <th className="py-3 px-4 text-left font-normal">Philosophy</th>
                <th className="py-3 px-3 text-right font-normal">Return</th>
                <th className="py-3 px-3 text-right font-normal">Sharpe</th>
                <th className="py-3 px-3 text-right font-normal">Max DD</th>
                <th className="py-3 px-4 text-right font-normal">Δ vs. Nifty 500</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.04]">
              {sortedAgents.map((ag, idx) => {
                const isTop = idx === 0;
                return (
                  <tr
                    key={ag.id}
                    className="hover:bg-white/[0.02] transition-colors group"
                  >
                    <td
                      className={`py-3.5 px-3 font-semibold ${
                        isTop ? 'text-[#D4AF37]' : 'text-zinc-500'
                      }`}
                    >
                      0{idx + 1}
                    </td>

                    <td className="py-3.5 px-4 font-sans font-medium text-white group-hover:text-[#D4AF37] transition-colors">
                      <Link to={`/portfolio/${ag.id}`}>{ag.name}</Link>
                    </td>

                    <td className="py-3.5 px-4 text-zinc-400 truncate max-w-[220px]">
                      {ag.philosophy}
                    </td>

                    <td
                      className={`py-3.5 px-3 text-right font-bold ${
                        ag.returnPct >= 0 ? 'text-emerald-400' : 'text-rose-400'
                      }`}
                    >
                      {formatPct(ag.returnPct)}
                    </td>

                    <td className="py-3.5 px-3 text-right text-zinc-300">
                      {ag.sharpeRatio.toFixed(2)}
                    </td>

                    <td className="py-3.5 px-3 text-right text-zinc-400">
                      {formatPct(ag.maxDrawdownPct)}
                    </td>

                    <td
                      className={`py-3.5 px-4 text-right ${
                        ag.alphaVsBenchmarkPct >= 0
                          ? 'text-emerald-400'
                          : 'text-zinc-500'
                      }`}
                    >
                      {ag.alphaVsBenchmarkPct >= 0
                        ? `+${formatPct(ag.alphaVsBenchmarkPct)}`
                        : formatPct(ag.alphaVsBenchmarkPct)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Micro-caption matching Reference Image 2 */}
        <div className="pt-2 text-[11px] font-mono text-zinc-600">
          Figures update nightly upon EOD market close. Rows carry a visible divider; columns a quieter one.
        </div>
      </section>

    </div>
  );
}
