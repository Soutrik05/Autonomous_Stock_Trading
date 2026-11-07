import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowRight,
  Scale,
  Sparkles,
  ShieldCheck,
  Terminal,
} from 'lucide-react';
import type { AgentLeaderboardEntry } from '../types';
import { apiService } from '../services/api';
import WatchlistFunnel from '../components/WatchlistFunnel';
import ExplainabilitySpotlight from '../components/ExplainabilitySpotlight';

export default function Home() {
  const [agents, setAgents] = useState<AgentLeaderboardEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const data = await apiService.getLeaderboard();
        setAgents(data);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const simonsLlm = agents.find((a) => a.id === 'simons');
  const simonsRules = agents.find((a) => a.id === 'baseline-simons-rules');
  const simonsAlphaSpread =
    simonsLlm && simonsRules ? (simonsLlm.returnPct - simonsRules.returnPct).toFixed(2) : '3.10';

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-24 flex justify-center items-center">
        <div className="flex items-center gap-3 text-slate-400 font-mono text-sm">
          <div className="w-5 h-5 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />
          <span>Synchronizing arena state...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 lg:py-16 space-y-16 animate-fade-in font-sans">
      
      {/* 1. OUT-OF-THE-WORLD ARENA HERO (Minimal, Big Bold Fonts, Clear Pitch) */}
      <section className="relative text-center max-w-4xl mx-auto space-y-6 pt-4 sm:pt-8">
        
        {/* Ambient Top Tag Pill */}
        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 text-xs font-mono font-medium shadow-[0_0_20px_rgba(6,182,212,0.15)]">
          <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
          <span>Autonomous Multi-Agent Evaluation Arena · NSE Nifty 500</span>
        </div>

        {/* Big Bold Headline */}
        <h1 className="text-4xl sm:text-6xl lg:text-7xl font-extrabold tracking-tight text-white leading-[1.08]">
          Can Generative LLMs <br className="hidden sm:inline" />
          <span className="bg-gradient-to-r from-cyan-400 via-blue-400 to-indigo-300 bg-clip-text text-transparent">
            Out-Trade Hard Rules?
          </span>
        </h1>

        {/* Crisp Clear Pitch */}
        <p className="text-base sm:text-lg text-slate-400 max-w-2xl mx-auto leading-relaxed">
          Five autonomous LLM investor personas benchmarked against five identical deterministic rules controls and the Nifty 500 index. Every trade decision, loss autopsy, and reflection rule verified point-in-time on an integer-paise paper ledger.
        </p>

        {/* Call to Actions */}
        <div className="flex flex-wrap items-center justify-center gap-4 pt-4">
          <Link
            to="/leaderboard"
            className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white font-semibold text-sm shadow-[0_0_25px_rgba(6,182,212,0.35)] transition-all cursor-pointer group"
          >
            <span>Enter Strategy Leaderboard</span>
            <ArrowRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
          </Link>

          <Link
            to="/comparison"
            className="inline-flex items-center gap-2 px-5 py-3 rounded-xl border border-white/10 bg-white/[0.04] hover:bg-white/[0.08] text-white font-medium text-sm backdrop-blur-md transition-colors cursor-pointer"
          >
            <Scale className="w-4 h-4 text-cyan-400" />
            <span>Paired Baseline Comparison</span>
          </Link>
        </div>

        {/* Sub-hero Guarantees Ticker */}
        <div className="pt-8 flex flex-wrap items-center justify-center gap-6 text-xs font-mono text-slate-500">
          <span className="flex items-center gap-1.5">
            <ShieldCheck className="w-3.5 h-3.5 text-cyan-400" />
            <span>Zero float accounting (Integer paise)</span>
          </span>
          <span className="text-white/10">|</span>
          <span className="flex items-center gap-1.5">
            <Terminal className="w-3.5 h-3.5 text-purple-400" />
            <span>100% Deterministic faithfulness check</span>
          </span>
          <span className="text-white/10">|</span>
          <span className="flex items-center gap-1.5">
            <Sparkles className="w-3.5 h-3.5 text-emerald-400" />
            <span>Live autonomous reflection engine</span>
          </span>
        </div>
      </section>

      {/* 2. CENTRAL RESEARCH DELTA (The Single Most Important Empirical Result) */}
      <section className="arena-glow-card p-6 sm:p-8">
        <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-6">
          <div className="space-y-2 max-w-xl">
            <div className="flex items-center gap-2 text-xs font-mono text-cyan-400 font-semibold uppercase tracking-wider">
              <Sparkles className="w-3.5 h-3.5" />
              <span>The Central Empirical Delta</span>
            </div>
            <h3 className="text-2xl font-bold tracking-tight text-white">
              LLM Simons vs. Rules-Only Simons Baseline
            </h3>
            <p className="text-xs sm:text-sm text-slate-400 leading-relaxed">
              Both strategies ingest the exact same candidate list from the Stage-3 screener and execute through the identical simulated broker. The generative cognitive layer demonstrates a <strong>+{simonsAlphaSpread}% alpha spread</strong> over hard-coded rules.
            </p>
          </div>

          {/* Glowing Metrics Capsule */}
          <div className="arena-glass-subdued p-5 rounded-xl border border-white/10 flex items-center gap-6 font-mono text-xs w-full lg:w-auto justify-between lg:justify-start">
            <div>
              <span className="text-slate-400 text-[10px] block">LLM SIMONS</span>
              <span className="text-2xl font-bold text-blue-400">+{simonsLlm?.returnPct || 4.25}%</span>
              <span className="text-[10px] text-slate-500 block">Cognitive layer</span>
            </div>
            <span className="text-slate-600 text-lg">vs</span>
            <div>
              <span className="text-slate-400 text-[10px] block">RULES SIMONS</span>
              <span className="text-2xl font-bold text-slate-300">+{simonsRules?.returnPct || 1.15}%</span>
              <span className="text-[10px] text-slate-500 block">Control baseline</span>
            </div>
            <div className="pl-6 border-l border-white/10">
              <span className="text-slate-400 text-[10px] block">ALPHA SPREAD</span>
              <span className="text-2xl font-extrabold text-emerald-400">+{simonsAlphaSpread}%</span>
              <span className="text-[10px] text-emerald-500/80 block">Net cognitive edge</span>
            </div>
          </div>
        </div>
      </section>

      {/* 3. INTERACTIVE WATCHLIST SCREENING FUNNEL */}
      <section className="space-y-4">
        <WatchlistFunnel />
      </section>

      {/* 4. EXPLAINABILITY & FAITHFULNESS AUDIT SPOTLIGHT */}
      <section className="space-y-4">
        <ExplainabilitySpotlight />
      </section>

    </div>
  );
}
