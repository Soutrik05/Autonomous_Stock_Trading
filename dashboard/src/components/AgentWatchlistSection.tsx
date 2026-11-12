import { ShieldCheck, Clock } from 'lucide-react';
import type { AgentWatchlistItem } from '../types';
import { SectionHeader } from './ui/SectionHeader';

interface AgentWatchlistSectionProps {
  watchlist: AgentWatchlistItem[];
  agentName: string;
}

export default function AgentWatchlistSection({
  watchlist,
  agentName,
}: AgentWatchlistSectionProps) {
  // Sort by intensity score descending
  const sorted = [...watchlist].sort((a, b) => b.intensityScore - a.intensityScore);
  const maxScore = Math.max(...sorted.map((item) => item.intensityScore), 1);

  return (
    <section className="border border-border-hairline bg-[#161616] rounded-lg overflow-hidden font-sans space-y-3 p-4 sm:p-5">
      {/* Section Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 border-b border-border-hairline pb-3">
        <SectionHeader
          title="Active Strategy Watchlist"
          tag="NIFTY 500 CONSTITUENTS"
          subtitle={`Screened high-intensity candidate setups queued for ${agentName}'s portfolio allocation.`}
        />

        <div className="text-[11px] font-mono text-zinc-400 flex items-center gap-2">
          <span>Universe: <strong className="text-zinc-200 font-normal">Nifty 500</strong></span>
          <span className="text-zinc-600">·</span>
          <span>{watchlist.length} Candidate{watchlist.length === 1 ? '' : 's'}</span>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto border border-border-hairline rounded">
        <table className="w-full text-left font-mono text-xs">
          <thead>
            <tr className="bg-[#121212] border-b border-border-hairline text-[10px] text-zinc-500 uppercase tracking-wider">
              <th className="py-2.5 px-4 font-normal">Asset</th>
              <th className="py-2.5 px-4 font-normal">Sector</th>
              <th className="py-2.5 px-4 font-normal text-right">Intensity / Conviction</th>
              <th className="py-2.5 px-4 font-normal">Added On</th>
              <th className="py-2.5 px-4 font-normal">TTL Window</th>
              <th className="py-2.5 px-4 font-normal text-right">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border-hairline text-zinc-300">
            {sorted.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-8 text-center text-zinc-500 text-xs">
                  No active candidates on watchlist. Strategy is currently selective.
                </td>
              </tr>
            ) : (
              sorted.map((item) => {
                const intensityRatio = Math.min(item.intensityScore / maxScore, 1);

                return (
                  <tr key={item.ticker} className="hover:bg-white/[0.02] transition-colors">
                    {/* Ticker & Company Name */}
                    <td className="py-2.5 px-4 font-sans">
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-semibold text-white text-xs">
                          {item.ticker}
                        </span>
                        <span className="text-zinc-400 text-xs truncate max-w-[180px] sm:max-w-[240px]">
                          {item.companyName}
                        </span>
                      </div>
                    </td>

                    {/* Sector */}
                    <td className="py-2.5 px-4 text-zinc-400 text-xs font-sans">
                      {item.sector}
                    </td>

                    {/* Intensity Score with subtle bar */}
                    <td className="py-2.5 px-4 text-right">
                      <div className="inline-flex flex-col items-end gap-1">
                        <span className="text-zinc-200 font-semibold tabular-nums text-xs">
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
                    <td className="py-2.5 px-4 text-zinc-400 text-[11px]">
                      {item.addedOn}
                    </td>

                    {/* TTL Days & Expiry */}
                    <td className="py-2.5 px-4 text-[11px]">
                      <div className="flex items-center gap-1.5 text-zinc-300">
                        <Clock className="w-3 h-3 text-zinc-500 flex-shrink-0" />
                        <span>{item.ttlDays}d TTL</span>
                        <span className="text-zinc-500">·</span>
                        <span className="text-zinc-400">Exp {item.expiresOn}</span>
                      </div>
                    </td>

                    {/* Status Badge */}
                    <td className="py-2.5 px-4 text-right">
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-emerald-500/10 text-positive border border-emerald-500/25">
                        <ShieldCheck className="w-3 h-3" />
                        <span>Queued</span>
                      </span>
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
