import type { AgentWatchlistItem } from '../types';
import { cn } from '../utils/cn';

interface AgentWatchlistSectionProps {
  watchlist: AgentWatchlistItem[];
  agentName?: string;
  lastRunDate?: string;
}

export default function AgentWatchlistSection({
  watchlist,
  lastRunDate,
}: AgentWatchlistSectionProps) {
  // Sort by intensity score descending
  const sorted = [...watchlist].sort((a, b) => b.intensityScore - a.intensityScore);
  const maxScore = Math.max(...sorted.map((item) => item.intensityScore), 1);

  return (
    <div className="glow-box rounded-lg">
    <section className="border border-border-hairline bg-[#161616] rounded-lg overflow-hidden font-sans">
      {/* Header */}
      <div className="p-4 sm:p-5 border-b border-border-hairline flex flex-col sm:flex-row sm:items-center justify-between gap-2 font-mono text-xs">
        <div className="flex items-center gap-2">
          <h3 className="font-display text-lg font-medium text-white tracking-tight">
            Active Watchlist
          </h3>
          <span className="px-2 py-0.5 rounded bg-white/[0.04] text-zinc-300 border border-border-hairline text-[11px]">
            {sorted.length} {sorted.length === 1 ? 'Candidate' : 'Candidates'}
          </span>
        </div>

        <div className="flex items-center gap-3 text-[11px] font-mono">
          <span className="text-zinc-400">
            Last Pipeline Run: <strong className="text-zinc-200">{lastRunDate || '2026-11-06 (EOD)'}</strong>
          </span>
          <span className="text-zinc-600">·</span>
          <span className="text-zinc-500">5d TTL Window</span>
        </div>
      </div>

      {/* Clean Table: Standardized to Leaderboard Grid */}
      <div className="overflow-x-auto border border-border-hairline bg-[#161616] rounded-lg">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-[#121212] border-b border-border-hairline text-xs sm:text-sm font-mono text-zinc-400 whitespace-nowrap">
              <th className="py-3 px-3.5 font-normal">Asset</th>
              <th className="py-3 px-3.5 font-normal">Sector</th>
              <th className="py-3 px-3.5 font-normal text-right">Setup Intensity</th>
              <th className="py-3 px-3.5 font-normal text-right">Added</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border-hairline text-base font-sans whitespace-nowrap">
            {sorted.length === 0 ? (
              <tr>
                <td colSpan={4} className="py-10 text-center font-mono text-zinc-500 text-sm">
                  No active candidates on watchlist. Screening pipeline runs daily at market close.
                </td>
              </tr>
            ) : (
              sorted.map((item, idx) => {
                const intensityRatio = Math.min(item.intensityScore / maxScore, 1);

                return (
                  <tr
                    key={item.ticker}
                    className={cn(
                      "transition-colors group hover:bg-white/[0.03]",
                      idx % 2 === 1 ? "bg-white/[0.01]" : "bg-transparent"
                    )}
                  >
                    {/* Ticker & Company Name */}
                    <td className="py-3 px-3.5">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-mono font-bold text-white text-base">
                          {item.ticker}
                        </span>
                        <span className="text-zinc-400 text-sm font-sans truncate max-w-[180px] sm:max-w-[280px]">
                          {item.companyName}
                        </span>
                      </div>
                    </td>

                    {/* Sector */}
                    <td className="py-3 px-3.5 text-zinc-300 text-sm sm:text-base font-sans">
                      {item.sector}
                    </td>

                    {/* Intensity Score */}
                    <td className="py-3 px-3.5 text-right">
                      <div className="inline-flex flex-col items-end gap-1">
                        <span className="text-white font-mono font-bold tabular-nums text-base">
                          {item.intensityScore.toFixed(2)}
                        </span>
                        <div className="w-16 h-1 bg-white/10 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-brand-blue rounded-full"
                            style={{ width: `${Math.max(intensityRatio * 100, 8)}%` }}
                          />
                        </div>
                      </div>
                    </td>

                    {/* Added Date */}
                    <td className="py-3 px-3.5 text-right text-zinc-400 font-mono text-sm sm:text-base tabular-nums">
                      {item.addedOn}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </section>
    </div>
  );
}
