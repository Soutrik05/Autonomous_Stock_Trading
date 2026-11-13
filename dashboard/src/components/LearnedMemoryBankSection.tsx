import type { HeuristicMemory } from '../types';
import { cn } from '../utils/cn';

interface LearnedMemoryBankSectionProps {
  heuristics: HeuristicMemory[];
}

export default function LearnedMemoryBankSection({ heuristics }: LearnedMemoryBankSectionProps) {
  return (
    <div className="bg-[#161616] border border-border-hairline rounded-lg font-sans overflow-hidden">
      {/* Header */}
      <div className="p-4 sm:p-5 border-b border-border-hairline flex items-center justify-between font-mono text-xs">
        <div className="flex items-center gap-2">
          <h3 className="font-serif text-lg font-medium text-white tracking-tight">
            Learned Heuristics
          </h3>
          <span className="px-2 py-0.5 rounded bg-white/[0.04] text-zinc-300 border border-border-hairline text-[11px]">
            {heuristics.length} {heuristics.length === 1 ? 'Rule' : 'Rules'}
          </span>
        </div>

        <span className="text-[11px] text-zinc-500 font-mono">
          Post-Mortem Rules
        </span>
      </div>

      {/* Rules Grid or Empty State */}
      <div className="p-4 sm:p-5">
        {heuristics.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {heuristics.map((h) => {
              const isSeek = h.kind === 'SEEK';

              return (
                <div
                  key={h.id}
                  className="bg-[#121212] border border-border-hairline hover:border-white/20 transition-all p-4 rounded-lg space-y-3 flex flex-col justify-between"
                >
                  <div className="space-y-2.5">
                    {/* Top Status */}
                    <div className="flex items-center justify-between text-xs font-mono">
                      <span
                        className={cn(
                          "px-2 py-0.5 rounded text-[10px] font-mono tracking-wider font-semibold border",
                          isSeek
                            ? "bg-emerald-500/10 text-positive border-emerald-500/25"
                            : "bg-rose-500/10 text-negative border-rose-500/25"
                        )}
                      >
                        {isSeek ? 'ALPHA RULE' : 'RISK FILTER'}
                      </span>
                      <span className="text-[11px] text-zinc-500">
                        {h.status}
                      </span>
                    </div>

                    {/* Rule Description */}
                    <p className="text-sm font-sans text-white leading-relaxed">
                      {h.ruleDescription}
                    </p>

                    {/* Trigger Code */}
                    {h.triggerPredicate && (
                      <div className="p-2 rounded bg-black/40 border border-white/5 text-[11px] font-mono text-zinc-300 break-all">
                        <span className="text-zinc-500 text-[10px] block uppercase font-sans mb-0.5">
                          Trigger Condition:
                        </span>
                        <code>{h.triggerPredicate}</code>
                      </div>
                    )}
                  </div>

                  {/* Empirical Track Record */}
                  <div className="flex items-center justify-between text-xs font-mono text-zinc-400 pt-2.5 border-t border-border-hairline">
                    <div className="flex items-center gap-1.5">
                      <span className="text-zinc-500 text-[11px]">Confidence:</span>
                      <strong className="text-white font-medium">
                        {(h.confidenceScore * 100).toFixed(0)}%
                      </strong>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <span className="text-zinc-500 text-[11px]">Track Record:</span>
                      <strong className="text-zinc-300 font-medium">
                        {h.timesApplied}x ({h.successRatePct.toFixed(0)}% win)
                      </strong>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="py-10 text-center font-mono text-xs text-zinc-400">
            No learned heuristics extracted yet. New rules generate upon post-mortem review of closed trade cycles.
          </div>
        )}
      </div>
    </div>
  );
}
