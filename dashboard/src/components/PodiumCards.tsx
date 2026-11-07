import { Link } from 'react-router-dom';
import { ArrowUpRight } from 'lucide-react';
import type { AgentLeaderboardEntry } from '../types';
import { formatPct } from '../utils/formatters';

interface PodiumCardsProps {
  topAgents: AgentLeaderboardEntry[];
}

export default function PodiumCards({ topAgents }: PodiumCardsProps) {
  const podiumStyles = [
    {
      rank: 1,
      badge: 'GOLD #1',
      badgeBg: 'bg-amber-100 text-amber-900 border-amber-300',
      border: 'border-amber-400/80 ring-1 ring-amber-400/20',
      sparkColor: '#D97706',
      iconColor: 'text-amber-500',
    },
    {
      rank: 2,
      badge: 'SILVER #2',
      badgeBg: 'bg-stone-200 text-stone-800 border-stone-300',
      border: 'border-stone-300',
      sparkColor: '#64748B',
      iconColor: 'text-stone-400',
    },
    {
      rank: 3,
      badge: 'BRONZE #3',
      badgeBg: 'bg-orange-100 text-orange-900 border-orange-300',
      border: 'border-orange-300',
      sparkColor: '#B45309',
      iconColor: 'text-orange-600',
    },
  ];

  const leaders = topAgents.slice(0, 3);

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {leaders.map((agent, i) => {
        const style = podiumStyles[i] || podiumStyles[2];
        return (
          <div
            key={agent.id}
            className={`porcelain-card p-5 transition-all hover:shadow-md relative flex flex-col justify-between ${style.border}`}
          >
            <div>
              {/* Card Header with Rank Pill */}
              <div className="flex justify-between items-center mb-3">
                <span
                  className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold border uppercase tracking-wider ${style.badgeBg}`}
                >
                  {style.badge}
                </span>

                <span className="text-[10px] font-mono text-[#9CA3AF]">
                  {agent.closedTrades} closed trades
                </span>
              </div>

              {/* Agent Identity */}
              <Link
                to={`/portfolio/${agent.id}`}
                className="group flex items-center justify-between"
              >
                <div>
                  <h4 className="font-serif font-bold text-lg text-[#111827] group-hover:text-amber-700 transition-colors">
                    {agent.name}
                  </h4>
                  <p className="text-xs text-[#4B5563] truncate max-w-[200px]">
                    {agent.philosophy}
                  </p>
                </div>
                <ArrowUpRight className="w-4 h-4 text-stone-400 opacity-0 group-hover:opacity-100 transition-opacity" />
              </Link>

              {/* Return Metrics */}
              <div className="mt-4 pt-3 border-t border-[#EDEAE2] flex items-baseline justify-between">
                <div>
                  <div className="text-[10px] uppercase font-mono text-[#9CA3AF]">Total Return</div>
                  <div className="text-2xl font-bold font-mono text-emerald-600">
                    {formatPct(agent.returnPct)}
                  </div>
                </div>

                <div className="text-right">
                  <div className="text-[10px] uppercase font-mono text-[#9CA3AF]">Alpha vs N500</div>
                  <div className="text-sm font-semibold font-mono text-emerald-600/90">
                    +{formatPct(agent.alphaVsBenchmarkPct)}
                  </div>
                </div>
              </div>
            </div>

            {/* Bottom active pick */}
            <div className="mt-4 pt-2.5 border-t border-[#EDEAE2] flex items-center justify-between text-xs font-mono">
              <span className="text-[#9CA3AF]">Top Pick:</span>
              <span className="font-bold text-[#111827] bg-[#F4F2EC] px-2 py-0.5 rounded border border-[#E5E2D9]">
                {agent.id === 'simons'
                  ? 'ANANDRATHI'
                  : agent.id === 'marks'
                  ? 'SCHAEFFLER'
                  : agent.id === 'jhunjhunwala'
                  ? 'CRISIL'
                  : 'HBLENGINE'}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
