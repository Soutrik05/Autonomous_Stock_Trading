import type { AgentWatchlistItem } from '../types';

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
    <section className="border border-border-hairline bg-[#161616] rounded-lg overflow-hidden font-sans">
      {/* Header */}
      <div className="p-4 sm:p-5 border-b border-border-hairline flex flex-col sm:flex-row sm:items-center justify-between gap-2 font-mono text-xs">
        <div className="flex items-center gap-2">
          <h3 className="font-serif text-lg font-medium text-white tracking-tight">
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

      {/* Clean Table: Zero Nested Borders */}
      <div className="overflow-x-auto">
        <table className="w-full text-left font-mono text-xs">
          <thead>
            <tr className="bg-[#121212] border-b border-border-hairline text-[10px] text-zinc-500 uppercase tracking-wider">
              <th className="py-3 px-4 sm:px-5 font-normal">Asset</th>
              <th className="py-3 px-4 sm:px-5 font-normal">Sector</th>
              <th className="py-3 px-4 sm:px-5 font-normal text-right">Setup Intensity</th>
              <th className="py-3 px-4 sm:px-5 font-normal text-right">Added</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border-hairline text-zinc-300">
            {sorted.length === 0 ? (
              <tr>
                <td colSpan={4} className="py-10 text-center text-zinc-400 text-xs">
                  No active candidates on watchlist. Screening pipeline runs daily at market close.
                </td>
              </tr>
            ) : (
              sorted.map((item) => {
                const intensityRatio = Math.min(item.intensityScore / maxScore, 1);

                return (
                  <tr key={item.ticker} className="hover:bg-white/[0.02] transition-colors">
                    {/* Ticker & Company Name */}
                    <td className="py-3 px-4 sm:px-5">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-mono font-bold text-white text-sm">
                          {item.ticker}
                        </span>
                        <span className="text-zinc-400 text-xs font-sans truncate max-w-[180px] sm:max-w-[280px]">
                          {item.companyName}
                        </span>
                      </div>
                    </td>

                    {/* Sector */}
                    <td className="py-3 px-4 sm:px-5 text-zinc-400 text-xs font-sans">
                      {item.sector}
                    </td>

                    {/* Intensity Score */}
                    <td className="py-3 px-4 sm:px-5 text-right">
                      <div className="inline-flex flex-col items-end gap-1">
                        <span className="text-white font-bold tabular-nums text-sm">
                          {item.intensityScore.toFixed(2)}
                        </span>
                        <div className="w-16 h-1 bg-white/10 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-accent rounded-full"
                            style={{ width: `${Math.max(intensityRatio * 100, 8)}%` }}
                          />
                        </div>
                      </div>
                    </td>

                    {/* Added Date */}
                    <td className="py-3 px-4 sm:px-5 text-right text-zinc-400 text-xs tabular-nums">
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
  );
}
