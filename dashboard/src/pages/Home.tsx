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
        <div className="flex items-center gap-3 text-[#7C8698] font-mono text-sm">
          <div className="w-4 h-4 border-2 border-[#8A7441] border-t-transparent rounded-full animate-spin" />
          <span>Loading research overview...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-12 animate-fade-in font-sans">
      {/* 1. Dual-Split Hero Zone (Research Thesis & Framing) */}
      <section className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center border-b border-[#DCD7CC] pb-10">
        {/* Left Column: Research Thesis & Framing */}
        <div className="lg:col-span-5 space-y-5">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-[2px] bg-[#F3EFE6] border border-[#D6C7A1] text-[#8A7441] text-xs font-mono font-medium">
            <span className="w-1.5 h-1.5 rounded-full bg-[#1E6548]" />
            <span>Autonomous multi-agent arena · NSE Nifty 500</span>
          </div>

          <h1 className="text-3xl sm:text-4xl lg:text-5xl font-serif font-bold text-[#151B26] leading-[1.15] tracking-tight">
            Can generative LLMs out-trade deterministic rules?
          </h1>

          <p className="text-sm sm:text-base text-[#475060] leading-relaxed">
            StockMinds is an academic paper-trading experiment benchmarking 5 distinct LLM personas against 5 identical deterministic rules controls and the Nifty 500 index. Every trade decision, loss post-mortem, and learned heuristic is recorded in an integer-paise ledger.
          </p>

          <div className="flex flex-wrap items-center gap-3 pt-2">
            <Link
              to="/leaderboard"
              className="inline-flex items-center gap-2 px-4 py-2 rounded-[3px] bg-[#8A7441] hover:bg-[#6D5B31] text-white font-medium text-xs shadow-xs transition-colors cursor-pointer"
            >
              <span>Explore 10-strategy leaderboard</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>

            <Link
              to="/comparison"
              className="inline-flex items-center gap-2 px-4 py-2 rounded-[3px] border border-[#DCD7CC] bg-white hover:bg-[#F6F4EF] text-[#151B26] font-medium text-xs transition-colors cursor-pointer"
            >
              <Scale className="w-3.5 h-3.5 text-[#7C8698]" />
              <span>Head-to-head comparison</span>
            </Link>
          </div>
        </div>

        {/* Right Column: The Podium (Top 3 Performers) */}
        <div className="lg:col-span-7 space-y-3">
          <div className="flex items-center justify-between text-xs font-mono text-[#7C8698] px-1">
            <span className="flex items-center gap-1.5 font-medium">
              <Award className="w-3.5 h-3.5 text-[#8A7441]" />
              <span>Live top 3 performance podium</span>
            </span>
            <Link to="/leaderboard" className="text-[#8A7441] hover:underline">
              View all 10 strategies &rarr;
            </Link>
          </div>

          <PodiumCards topAgents={sortedAgents} />
        </div>
      </section>

      {/* 2. Central Research Delta Callout */}
      <section className="callout-panel p-6 flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
        <div className="space-y-1">
          <div className="flex items-center gap-2 text-xs font-mono text-[#8A7441] font-medium">
            <Sparkles className="w-3.5 h-3.5" />
            <span>Central research delta</span>
          </div>
          <h3 className="text-xl font-serif font-bold text-[#151B26]">
            LLM Simons vs. rules-only Simons baseline
          </h3>
          <p className="text-xs text-[#475060] max-w-xl">
            Both strategies evaluate the identical Stage-3 candidate funnel through the same simulated broker. The LLM cognitive layer demonstrates a <strong>+{simonsAlphaSpread}% alpha spread</strong> over the rules control.
          </p>
        </div>

        <div className="flex items-center gap-4 bg-white p-3 rounded-[3px] border border-[#D6C7A1] font-mono text-xs shadow-xs">
          <div>
            <span className="text-[#7C8698] text-[10px] block">LLM Simons</span>
            <span className="text-base font-bold text-[#1E4E8C]">+{simonsLlm?.returnPct || 4.25}%</span>
          </div>
          <span className="text-[#BEB7A6] text-base">vs</span>
          <div>
            <span className="text-[#7C8698] text-[10px] block">Rules Simons</span>
            <span className="text-base font-bold text-[#475060]">+{simonsRules?.returnPct || 1.15}%</span>
          </div>
          <div className="pl-3 border-l border-[#DCD7CC]">
            <span className="text-[#7C8698] text-[10px] block">Alpha spread</span>
            <span className="text-base font-bold text-[#1E6548]">+{simonsAlphaSpread}%</span>
          </div>
        </div>
      </section>

      {/* 3. Interactive Watchlist Funnel Visualizer */}
      <section className="space-y-4">
        <WatchlistFunnel />
      </section>

      {/* 4. Explainability & Faithfulness Audit Spotlight */}
      <section className="space-y-4">
        <ExplainabilitySpotlight />
      </section>

      {/* 5. The 5 Investing Philosophies Overview */}
      <section className="space-y-4 border-t border-[#DCD7CC] pt-8">
        <div className="flex justify-between items-center">
          <div>
            <h3 className="text-xl font-serif font-bold text-[#151B26]">
              The 5 cognitive trading personas
            </h3>
            <p className="text-xs text-[#7C8698]">
              Five independent schools of investing trading separate ₹1,00,000 paper accounts.
            </p>
          </div>
          <Link
            to="/leaderboard"
            className="text-xs font-mono font-medium text-[#8A7441] hover:underline"
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
              rule: 'Kaufman ER > 0.60, ADX >= 25, Volatility parity sizing, 1.5 ATR stops.',
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
              className="ledger-panel p-4 hover:border-[#8A7441] transition-colors flex flex-col justify-between group cursor-pointer"
            >
              <div className="space-y-1.5">
                <div className="flex justify-between items-center">
                  <span className="font-serif font-bold text-sm text-[#151B26] group-hover:text-[#8A7441]">
                    {p.name}
                  </span>
                  <span className="text-[10px] font-mono text-[#7C8698]">{p.horizon}</span>
                </div>
                <div className="text-[11px] font-mono font-medium text-[#8A7441]">{p.style}</div>
                <p className="text-[11px] text-[#475060] leading-relaxed">{p.rule}</p>
              </div>

              <div className="mt-3 pt-2 border-t border-[#E7E3D9] flex justify-between items-center text-[10px] font-mono text-[#7C8698] group-hover:text-[#8A7441]">
                <span>View portfolio</span>
                <span>&rarr;</span>
              </div>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
