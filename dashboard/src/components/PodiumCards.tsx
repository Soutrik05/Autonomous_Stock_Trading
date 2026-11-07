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
      badgeClass: 'bg-[#F3EFE6] text-[#8A7441] border-[#D6C7A1]',
      borderClass: 'border-[#8A7441]/60',
    },
    {
      label: 'Rank 2 · Runner Up',
      badgeClass: 'bg-[#F6F4EF] text-[#475060] border-[#DCD7CC]',
      borderClass: 'border-[#DCD7CC]',
    },
    {
      label: 'Rank 3 · Contender',
      badgeClass: 'bg-[#F6F4EF] text-[#7C8698] border-[#DCD7CC]',
      borderClass: 'border-[#DCD7CC]',
    },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {leaders.map((agent, i) => {
        const style = rankAccents[i] || rankAccents[2];
        const isPositiveReturn = agent.returnPct >= 0;
        const isPositiveAlpha = agent.alphaVsBenchmarkPct >= 0;

        return (
          <div
            key={agent.id}
            className={`ledger-panel p-5 relative flex flex-col justify-between transition-colors hover:bg-[#FAF9F6] ${style.borderClass}`}
          >
            <div>
              {/* Card Meta Bar with Sentence Case Rank */}
              <div className="flex justify-between items-center mb-3">
                <span
                  className={`px-2 py-0.5 rounded-[2px] text-[10px] font-mono font-medium border ${style.badgeClass}`}
                >
                  {style.label}
                </span>

                <span className="text-[11px] font-mono text-[#7C8698]">
                  {agent.closedTrades} closed trades
                </span>
              </div>

              {/* Agent Identity */}
              <Link
                to={`/portfolio/${agent.id}`}
                className="group flex items-start justify-between mt-1"
              >
                <div>
                  <h4 className="font-serif font-bold text-lg text-[#151B26] group-hover:text-[#8A7441] transition-colors leading-tight">
                    {agent.name}
                  </h4>
                  <p className="text-xs text-[#475060] truncate max-w-[220px] mt-0.5">
                    {agent.philosophy}
                  </p>
                </div>
                <ArrowUpRight className="w-4 h-4 text-[#7C8698] group-hover:text-[#8A7441] transition-colors mt-0.5" />
              </Link>

              {/* Return Metrics */}
              <div className="mt-4 pt-3 border-t border-[#E7E3D9] flex items-baseline justify-between">
                <div>
                  <div className="text-[11px] font-sans text-[#7C8698]">Total return</div>
                  <div
                    className={`text-2xl font-bold font-mono tracking-tight ${
                      isPositiveReturn ? 'text-[#1E6548]' : 'text-[#933835]'
                    }`}
                  >
                    {formatPct(agent.returnPct)}
                  </div>
                </div>

                <div className="text-right">
                  <div className="text-[11px] font-sans text-[#7C8698]">Alpha vs Nifty 500</div>
                  <div
                    className={`text-sm font-semibold font-mono ${
                      isPositiveAlpha ? 'text-[#1E6548]' : 'text-[#933835]'
                    }`}
                  >
                    {isPositiveAlpha ? `+${formatPct(agent.alphaVsBenchmarkPct)}` : formatPct(agent.alphaVsBenchmarkPct)}
                  </div>
                </div>
              </div>
            </div>

            {/* Bottom active pick */}
            <div className="mt-4 pt-2.5 border-t border-[#E7E3D9] flex items-center justify-between text-xs font-mono">
              <span className="text-[#7C8698]">Target horizon:</span>
              <span className="font-medium text-[#151B26] bg-[#F6F4EF] px-2 py-0.5 rounded-[2px] border border-[#DCD7CC]">
                {agent.horizonDays}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
