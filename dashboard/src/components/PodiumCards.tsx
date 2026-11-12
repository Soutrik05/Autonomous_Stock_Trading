import { Link } from 'react-router-dom';
import { ArrowUpRight } from 'lucide-react';
import type { AgentLeaderboardEntry } from '../types';
import { formatPct } from '../utils/formatters';

interface PodiumCardsProps {
  topAgents: AgentLeaderboardEntry[];
}

export default function PodiumCards({ topAgents }: PodiumCardsProps) {
  const leaders = topAgents.slice(0, 3);

  const rankAccents = [
    {
      label: 'Rank 1 · Top Alpha',
      badgeClass: 'bg-[#D4AF37]/10 text-[#D4AF37] border-[#D4AF37]/30',
      borderClass: 'border-[#D4AF37]/50',
    },
    {
      label: 'Rank 2 · Runner Up',
      badgeClass: 'bg-white/[0.04] text-zinc-300 border-white/10',
      borderClass: 'border-white/[0.12]',
    },
    {
      label: 'Rank 3 · Contender',
      badgeClass: 'bg-white/[0.04] text-zinc-400 border-white/10',
      borderClass: 'border-white/[0.08]',
    },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
      {leaders.map((agent, i) => {
        const style = rankAccents[i] || rankAccents[2];
        const isPositiveReturn = agent.returnPct >= 0;
        const isPositiveAlpha = agent.alphaVsBenchmarkPct >= 0;

        return (
          <div
            key={agent.id}
            className={`border bg-[#1E1E1E] p-4 rounded transition-colors hover:border-white/20 flex flex-col justify-between space-y-3 font-mono text-xs ${style.borderClass}`}
          >
            <div>
              {/* Rank Label & Closed Trades */}
              <div className="flex justify-between items-center pb-2 border-b border-white/[0.06]">
                <span
                  className={`px-1.5 py-0.2 rounded text-[10px] font-medium border uppercase tracking-wider ${style.badgeClass}`}
                >
                  {style.label}
                </span>

                <span className="text-[11px] text-zinc-500">
                  {agent.closedTrades} trades
                </span>
              </div>

              {/* Agent Identity */}
              <Link
                to={`/portfolio/${agent.id}`}
                className="group flex items-start justify-between mt-2.5"
              >
                <div>
                  <h4 className="font-display font-medium text-base text-white group-hover:text-[#D4AF37] transition-colors leading-tight font-sans">
                    {agent.name}
                  </h4>
                  <span className="text-[11px] text-zinc-400 block mt-0.5">
                    {agent.horizonDays} Horizon
                  </span>
                </div>
                <ArrowUpRight className="w-3.5 h-3.5 text-zinc-500 group-hover:text-[#D4AF37] transition-colors" />
              </Link>

              {/* Return Metrics */}
              <div className="mt-3 pt-2.5 border-t border-white/[0.06] flex items-baseline justify-between">
                <div>
                  <div className="text-[10px] uppercase tracking-wider text-zinc-500">Return</div>
                  <div
                    className={`text-xl font-bold tabular-nums tracking-tight ${
                      isPositiveReturn ? 'text-emerald-400' : 'text-rose-400'
                    }`}
                  >
                    {formatPct(agent.returnPct)}
                  </div>
                </div>

                <div className="text-right">
                  <div className="text-[10px] uppercase tracking-wider text-zinc-500">Alpha vs Index</div>
                  <div
                    className={`text-sm font-semibold tabular-nums ${
                      isPositiveAlpha ? 'text-emerald-400' : 'text-rose-400'
                    }`}
                  >
                    {isPositiveAlpha ? `+${formatPct(agent.alphaVsBenchmarkPct)}` : formatPct(agent.alphaVsBenchmarkPct)}
                  </div>
                </div>
              </div>
            </div>

            {/* Bottom Target Horizon & Sharpe */}
            <div className="pt-2 border-t border-white/[0.06] flex items-center justify-between text-[11px] text-zinc-400">
              <span>Sharpe: <strong className="text-white font-medium">{agent.sharpeRatio.toFixed(2)}</strong></span>
              <span>Win Rate: <strong className="text-white font-medium">{agent.winRatePct.toFixed(1)}%</strong></span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
