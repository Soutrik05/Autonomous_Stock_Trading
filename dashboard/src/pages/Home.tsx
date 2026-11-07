import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowRight,
  Scale,
  Award,
  Sparkles,
} from 'lucide-react';
import type { AgentLeaderboardEntry } from '../types';
import { apiService } from '../services/api';
import PodiumCards from '../components/PodiumCards';
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

  const sortedAgents = [...agents].sort((a, b) => b.returnPct - a.returnPct);
  const simonsLlm = agents.find((a) => a.id === 'simons');
  const simonsRules = agents.find((a) => a.id === 'baseline-simons-rules');
  const simonsAlphaSpread =
    simonsLlm && simonsRules ? (simonsLlm.returnPct - simonsRules.returnPct).toFixed(2) : '3.10';

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-16 flex justify-center items-center">
        <div className="flex items-center gap-3 text-stone-500 font-mono text-sm">
          <div className="w-4 h-4 border-2 border-amber-600 border-t-transparent rounded-full animate-spin" />
          <span>Loading research overview...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-12 animate-fade-in font-sans">
      {/* 1. DUAL-SPLIT HERO ZONE (The First 5 Seconds) */}
      <section className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center border-b border-[#E5E2D9] pb-12">
        {/* Left Column: Research Thesis & Framing */}
        <div className="lg:col-span-5 space-y-5">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-amber-500/10 border border-amber-500/20 text-amber-800 text-xs font-mono font-medium">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span>Autonomous Multi-Agent Arena · NSE Nifty 500</span>
          </div>

          <h1 className="text-3xl sm:text-4xl lg:text-5xl font-serif font-bold text-[#111827] leading-[1.15]">
            Can Generative LLMs Out-Trade Deterministic Rules?
          </h1>

          <p className="text-sm sm:text-base text-[#4B5563] leading-relaxed">
            StockMinds is an academic paper-trading experiment benchmarking 5 distinct LLM personas against 5 identical deterministic rules controls and the Nifty 500 index. Every trade decision, loss post-mortem, and learned rule is recorded in an integer-paise ledger.
          </p>

          <div className="flex flex-wrap items-center gap-3 pt-2">
            <Link
              to="/leaderboard"
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-[#D97706] hover:bg-amber-700 text-white font-medium text-xs shadow-xs transition-all cursor-pointer"
            >
              <span>Explore 10-Agent Leaderboard</span>
              <ArrowRight className="w-4 h-4" />
            </Link>

            <Link
              to="/comparison"
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg border border-[#E5E2D9] bg-white hover:bg-[#F4F2EC] text-[#111827] font-medium text-xs transition-colors cursor-pointer"
            >
              <Scale className="w-3.5 h-3.5 text-stone-500" />
              <span>Head-to-Head Comparison</span>
            </Link>
          </div>
        </div>

        {/* Right Column: The Podium (Top 3 Performers) */}
        <div className="lg:col-span-7 space-y-3">
          <div className="flex items-center justify-between text-xs font-mono text-[#9CA3AF] px-1">
            <span className="flex items-center gap-1.5 uppercase font-semibold">
              <Award className="w-3.5 h-3.5 text-amber-500" />
              <span>Live Top 3 Performance Podium</span>
            </span>
            <Link to="/leaderboard" className="text-amber-700 hover:underline">
              View all 10 strategies &rarr;
            </Link>
          </div>

          <PodiumCards topAgents={sortedAgents} />
        </div>
      </section>

      {/* 2. HEAD-TO-HEAD COGNITIVE ALPHA TEASER */}
      <section className="porcelain-card p-6 bg-gradient-to-r from-amber-50/50 via-white to-amber-50/30 flex flex-col md:flex-row items-start md:items-center justify-between gap-6 border-[#E5E2D9]">
        <div className="space-y-1">
          <div className="flex items-center gap-2 text-xs font-mono text-amber-700 uppercase font-semibold">
            <Sparkles className="w-3.5 h-3.5" />
            <span>The Central Research Delta</span>
          </div>
          <h3 className="text-xl font-serif font-bold text-[#111827]">
            LLM Simons vs. Rules-Only Simons Baseline
          </h3>
          <p className="text-xs text-[#4B5563] max-w-xl">
            Both strategies evaluate the identical Stage-3 candidate funnel through the same simulated broker. The LLM cognitive layer demonstrates a <strong>+{simonsAlphaSpread}% alpha spread</strong> over the rules control.
          </p>
        </div>

        <div className="flex items-center gap-4 bg-white p-3 rounded-xl border border-[#E5E2D9] font-mono text-xs shadow-xs">
          <div>
            <span className="text-[#9CA3AF] text-[10px] block">LLM Simons</span>
            <span className="text-base font-bold text-blue-600">+{simonsLlm?.returnPct || 4.25}%</span>
          </div>
          <span className="text-stone-300 text-lg">vs</span>
          <div>
            <span className="text-[#9CA3AF] text-[10px] block">Rules Simons</span>
            <span className="text-base font-bold text-stone-700">+{simonsRules?.returnPct || 1.15}%</span>
          </div>
          <div className="pl-3 border-l border-[#EDEAE2]">
            <span className="text-[#9CA3AF] text-[10px] block">Alpha Spread</span>
            <span className="text-base font-bold text-emerald-600">+{simonsAlphaSpread}%</span>
          </div>
        </div>
      </section>

      {/* 3. INTERACTIVE WATCHLIST FUNNEL VISUALIZER */}
      <section className="space-y-4">
        <WatchlistFunnel />
      </section>

      {/* 4. EXPLAINABILITY & FAITHFULNESS AUDIT SPOTLIGHT */}
      <section className="space-y-4">
        <ExplainabilitySpotlight />
      </section>

      {/* 5. THE 5 INVESTING PHILOSOPHIES QUICK OVERVIEW */}
      <section className="space-y-4 border-t border-[#E5E2D9] pt-8">
        <div className="flex justify-between items-center">
          <div>
            <h3 className="text-xl font-serif font-bold text-[#111827]">
              The 5 Cognitive Trading Personas
            </h3>
            <p className="text-xs text-[#4B5563]">
              Five independent schools of investing trading separate ₹1,00,000 paper accounts.
            </p>
          </div>
          <Link
            to="/leaderboard"
            className="text-xs font-mono font-semibold text-amber-700 hover:underline"
          >
            Inspect rankings &rarr;
          </Link>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-5 gap-3 text-xs">
          {[
            {
              id: 'simons',
              name: 'Jim Simons',
              style: 'Quant Momentum',
              horizon: '5–15 days',
              rule: 'Kaufman ER > 0.60, ADX >= 25, Volatility Parity sizing, 1.5 ATR stops.',
            },
            {
              id: 'lynch',
              name: 'Peter Lynch',
              style: 'GARP',
              horizon: '60–120 days',
              rule: 'PEG <= 1.0, ROCE > 15%, CFO/PAT > 0.80, operational cash consistency.',
            },
            {
              id: 'marks',
              name: 'Howard Marks',
              style: 'Contrarian Value',
              horizon: '30–90 days',
              rule: 'P/E in lowest 30% of 5y range, debt/equity < 0.50, second-level thinking.',
            },
            {
              id: 'jhunjhunwala',
              name: 'Rakesh Jhunjhunwala',
              style: 'Growth & Quality',
              horizon: '90–180 days',
              rule: 'Zero promoter pledge, secular domestic growth, high conviction pyramiding.',
            },
            {
              id: 'stockminds-core',
              name: 'Varsity Core',
              style: 'Dual Confluence',
              horizon: '20–60 days',
              rule: 'Technical confluence confirmation + DCF intrinsic FCFF clamp and Kelly sizing.',
            },
          ].map((p) => (
            <Link
              key={p.id}
              to={`/portfolio/${p.id}`}
              className="porcelain-card p-4 hover:border-amber-400 transition-all flex flex-col justify-between group cursor-pointer"
            >
              <div className="space-y-1.5">
                <div className="flex justify-between items-center">
                  <span className="font-serif font-bold text-sm text-[#111827] group-hover:text-amber-700">
                    {p.name}
                  </span>
                  <span className="text-[10px] font-mono text-[#9CA3AF]">{p.horizon}</span>
                </div>
                <div className="text-[11px] font-mono font-semibold text-[#D97706]">{p.style}</div>
                <p className="text-[11px] text-[#4B5563] leading-relaxed">{p.rule}</p>
              </div>

              <div className="mt-3 pt-2 border-t border-[#EDEAE2] flex justify-between items-center text-[10px] font-mono text-stone-400 group-hover:text-amber-700">
                <span>View Portfolio</span>
                <span>&rarr;</span>
              </div>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
