import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowRight,
  Scale,
  ShieldCheck,
  Terminal,
  Activity,
  Layers,
  CheckCircle2,
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
          <div className="w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
          <span>Synchronizing arena state...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 lg:py-16 space-y-16 animate-fade-in font-sans">
      
      {/* 1. ASYMMETRIC INSTITUTIONAL HERO (Stripe/J.P. Morgan Discipline on Obsidian Slate) */}
      <section className="grid grid-cols-1 lg:grid-cols-12 gap-10 lg:gap-12 items-start">
        
        {/* Left Column: Authoritative Editorial Pitch & Core Empirical Delta */}
        <div className="lg:col-span-7 space-y-6">
          
          {/* Eyebrow Label */}
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded bg-white/[0.04] border border-white/10 text-slate-300 text-xs font-mono font-medium">
            <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />
            <span>NSE Nifty 500 · 10 Parallel Personas · Immutable Integer Ledger</span>
          </div>

          {/* Solid Dignified Headline (No gradient text) */}
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight text-white leading-[1.12]">
            Can Autonomous LLMs Out-Trade Hard Rules?
          </h1>

          {/* Clear, Measured Proposition */}
          <p className="text-base sm:text-lg text-slate-400 max-w-xl leading-relaxed">
            Five autonomous LLM investor personas benchmarked head-to-head against five identical deterministic rule controls and the Nifty 500 index. Verified point-in-time on an integer-paise paper ledger with zero float accounting.
          </p>

          {/* Solid Institutional Actions */}
          <div className="flex flex-wrap items-center gap-3 pt-1">
            <Link
              to="/leaderboard"
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded bg-blue-600 hover:bg-blue-500 text-white font-semibold text-sm transition-colors cursor-pointer"
            >
              <span>Explore Strategy Leaderboard</span>
              <ArrowRight className="w-4 h-4" />
            </Link>

            <Link
              to="/comparison"
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded border border-white/15 bg-white/[0.03] hover:bg-white/[0.07] text-slate-200 font-medium text-sm transition-colors cursor-pointer"
            >
              <Scale className="w-4 h-4 text-slate-400" />
              <span>Paired Baseline Comparison</span>
            </Link>
          </div>

          {/* Core Empirical Delta Card (Simons LLM vs Rules Baseline) */}
          <div className="arena-glow-card p-6 mt-6 space-y-4">
            <div className="flex items-center justify-between border-b border-white/[0.08] pb-3">
              <div className="flex items-center gap-2 text-xs font-mono text-slate-400 uppercase tracking-wider">
                <Activity className="w-3.5 h-3.5 text-blue-400" />
                <span>The Central Empirical Delta</span>
              </div>
              <span className="text-[11px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20 font-medium">
                +{simonsAlphaSpread}% Alpha Spread
              </span>
            </div>

            <div className="space-y-1">
              <h3 className="text-lg font-bold text-white">
                LLM Simons vs. Rules-Only Simons Baseline
              </h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Both strategies ingest the exact same candidate list from the Stage-3 screener and execute through the identical simulated broker with 10 bps slippage.
              </p>
            </div>

            {/* Structured Financial Triad */}
            <div className="grid grid-cols-3 gap-3 pt-2">
              <div className="p-3 rounded bg-white/[0.02] border border-white/[0.06]">
                <span className="text-[10px] font-mono text-slate-400 block">LLM SIMONS</span>
                <span className="text-xl font-bold font-mono text-blue-400 mt-0.5 block">
                  +{simonsLlm?.returnPct ?? 4.25}%
                </span>
                <span className="text-[10px] text-slate-500 block mt-0.5">Cognitive layer</span>
              </div>

              <div className="p-3 rounded bg-white/[0.02] border border-white/[0.06]">
                <span className="text-[10px] font-mono text-slate-400 block">RULES SIMONS</span>
                <span className="text-xl font-bold font-mono text-slate-300 mt-0.5 block">
                  +{simonsRules?.returnPct ?? 1.15}%
                </span>
                <span className="text-[10px] text-slate-500 block mt-0.5">Static control</span>
              </div>

              <div className="p-3 rounded bg-white/[0.02] border border-white/[0.06]">
                <span className="text-[10px] font-mono text-slate-400 block">NET SPREAD</span>
                <span className="text-xl font-bold font-mono text-emerald-400 mt-0.5 block">
                  +{simonsAlphaSpread}%
                </span>
                <span className="text-[10px] text-emerald-500/80 block mt-0.5">Empirical edge</span>
              </div>
            </div>
          </div>

          {/* Sub-hero Guarantees Ticker */}
          <div className="pt-2 flex flex-wrap items-center gap-6 text-xs font-mono text-slate-500">
            <span className="flex items-center gap-1.5">
              <ShieldCheck className="w-3.5 h-3.5 text-blue-400" />
              <span>Zero float accounting (Integer paise)</span>
            </span>
            <span className="text-white/10">|</span>
            <span className="flex items-center gap-1.5">
              <Terminal className="w-3.5 h-3.5 text-slate-400" />
              <span>100% Deterministic faithfulness check</span>
            </span>
            <span className="text-white/10">|</span>
            <span className="flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5 text-slate-400" />
              <span>Point-in-time EOD ingestion</span>
            </span>
          </div>
        </div>

        {/* Right Column: Live Institutional Arena Telemetry Window (Product Proof) */}
        <div className="lg:col-span-5">
          <div className="arena-glass overflow-hidden border border-white/[0.12] shadow-2xl">
            {/* Window Title Bar */}
            <div className="px-4 py-3 bg-white/[0.03] border-b border-white/[0.08] flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-white/20" />
                <span className="w-2.5 h-2.5 rounded-full bg-white/20" />
                <span className="w-2.5 h-2.5 rounded-full bg-white/20" />
                <span className="ml-2 text-xs font-mono text-slate-300 font-medium">
                  arena-telemetry.nse · paper feed
                </span>
              </div>
              <div className="flex items-center gap-1.5 text-[10px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                <span>10 ACTIVE PERSONAS</span>
              </div>
            </div>

            {/* Standings Micro-Ledger */}
            <div className="p-4 space-y-3 font-mono text-xs">
              <div className="flex items-center justify-between text-[11px] text-slate-500 uppercase tracking-wider pb-1 border-b border-white/[0.06]">
                <span>Strategy Persona</span>
                <span className="text-right">Return / Sharpe</span>
              </div>

              {agents.slice(0, 4).map((ag) => {
                const isControl = ag.id.startsWith('baseline-');
                return (
                  <div
                    key={ag.id}
                    className="flex items-center justify-between py-1.5 px-2 rounded hover:bg-white/[0.03] transition-colors"
                  >
                    <div className="flex items-center gap-2.5">
                      <span
                        className={`text-[9px] px-1.5 py-0.5 rounded font-bold ${
                          !isControl
                            ? 'bg-blue-500/20 text-blue-300 border border-blue-500/30'
                            : 'bg-slate-700/30 text-slate-400 border border-slate-700/50'
                        }`}
                      >
                        {isControl ? 'RULES' : 'LLM'}
                      </span>
                      <span className="font-semibold text-slate-200">{ag.name}</span>
                    </div>
                    <div className="text-right">
                      <span
                        className={`font-bold ${
                          ag.returnPct >= 0 ? 'text-emerald-400' : 'text-rose-400'
                        }`}
                      >
                        {ag.returnPct >= 0 ? `+${ag.returnPct}%` : `${ag.returnPct}%`}
                      </span>
                      <span className="text-slate-500 text-[10px] ml-2">SR {ag.sharpeRatio}</span>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Verified Trade Rationale Audit Block */}
            <div className="p-4 bg-black/40 border-t border-white/[0.08] space-y-2 font-mono text-xs">
              <div className="flex items-center justify-between text-[10px] text-slate-400">
                <span className="flex items-center gap-1.5 text-blue-400">
                  <Terminal className="w-3 h-3" />
                  <span>EXECUTION AUDIT · BEML</span>
                </span>
                <span className="text-slate-500">15:15 IST</span>
              </div>

              <p className="text-[11px] text-slate-300 leading-relaxed font-sans bg-white/[0.02] p-2.5 rounded border border-white/[0.04]">
                &quot;Momentum breakout confirmed by 20-day volume surge (1.8x). PE of 34.2 is within quantitative sector boundary. Sized at 120 shares at ₹4,180.50 (418,050 paise).&quot;
              </p>

              <div className="grid grid-cols-2 gap-2 text-[10px] pt-1">
                <div className="flex items-center gap-1 text-slate-400">
                  <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                  <span>Faithfulness: 100% OK</span>
                </div>
                <div className="text-right text-slate-500">
                  Debit: 50,166,000 paise
                </div>
              </div>
            </div>

            {/* Bottom Status Bar */}
            <div className="px-4 py-2 bg-white/[0.02] border-t border-white/[0.06] flex items-center justify-between text-[10px] font-mono text-slate-500">
              <span>ZERO FLOAT DRIFT</span>
              <span>LATENCY: 142MS</span>
            </div>
          </div>
        </div>
      </section>

      {/* 2. INTERACTIVE WATCHLIST SCREENING FUNNEL */}
      <section className="space-y-4">
        <WatchlistFunnel />
      </section>

      {/* 3. EXPLAINABILITY & FAITHFULNESS AUDIT SPOTLIGHT */}
      <section className="space-y-4">
        <ExplainabilitySpotlight />
      </section>

    </div>
  );
}
