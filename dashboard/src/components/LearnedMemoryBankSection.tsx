import type { HeuristicMemory } from '../types';
import { SectionHeader } from './ui/SectionHeader';
import { cn } from '../utils/cn';

interface LearnedMemoryBankSectionProps {
  heuristics: HeuristicMemory[];
}

export default function LearnedMemoryBankSection({ heuristics }: LearnedMemoryBankSectionProps) {
  return (
    <div className="space-y-4 font-sans">
      {/* Section Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2 border-b border-border-hairline pb-3">
        <SectionHeader
          title="Learned Memory Bank"
          tag="CAUSAL HEURISTICS"
          subtitle="Causal heuristics extracted from closed trade post-mortems via weekly reflection cycles."
        />
        <span className="text-xs font-mono px-2 py-0.5 rounded bg-white/[0.04] text-zinc-300 border border-border-hairline font-normal">
          {heuristics.length} {heuristics.length === 1 ? 'Rule' : 'Rules'} Active
        </span>
      </div>

      {/* Heuristic Rules Ledger */}
      {heuristics.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {heuristics.map((h) => {
            const isSeek = h.kind === 'SEEK';

            return (
              <div
                key={h.id}
                className="bg-[#121212] border border-border-hairline hover:border-white/20 transition-all p-5 rounded space-y-3.5 flex flex-col justify-between"
              >
                <div className="space-y-3">
                  {/* Top Meta Strip */}
                  <div className="flex items-center justify-between text-xs font-mono">
                    <span
                      className={cn(
                        "px-2 py-0.5 rounded text-[10px] font-mono tracking-wider font-medium border",
                        isSeek
                          ? "bg-emerald-500/10 text-positive border-emerald-500/25"
                          : "bg-rose-500/10 text-negative border-rose-500/25"
                      )}
                    >
                      {isSeek ? 'ALPHA RULE' : 'RISK FILTER'}
                    </span>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-white/[0.04] text-zinc-400 border border-border-hairline">
                      STATUS: {h.status}
                    </span>
                  </div>

                  {/* Core Heuristic Thesis */}
                  <p className="text-sm font-sans font-normal text-white leading-relaxed">
                    {h.ruleDescription}
                  </p>

                  {/* Trigger Predicate */}
                  {h.triggerPredicate && (
                    <div className="text-xs font-mono text-zinc-300 bg-white/[0.02] border-l-2 border-border-hairline pl-3 py-1.5 space-y-0.5">
                      <span className="text-[10px] text-zinc-500 uppercase tracking-wider block font-sans">
                        Trigger Expression:
                      </span>
                      <code className="text-zinc-200 text-[11px] block break-all">
                        {h.triggerPredicate}
                      </code>
                    </div>
                  )}
                </div>

                {/* Empirical Track Record & Confidence Strip */}
                <div className="flex items-center justify-between text-xs font-mono text-zinc-400 pt-3 border-t border-border-hairline">
                  <div className="flex items-center gap-1.5">
                    <span className="text-zinc-500 text-[11px]">Confidence:</span>
                    <strong className="text-white font-medium">
                      {(h.confidenceScore * 100).toFixed(0)}%
                    </strong>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="text-zinc-500 text-[11px]">Sample:</span>
                    <strong className="text-zinc-200 font-medium">
                      {h.timesApplied}x ({h.successRatePct.toFixed(0)}% win)
                    </strong>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        /* State when 0 heuristics in early pilot */
        <div className="p-8 text-center bg-[#121212] border border-border-hairline rounded space-y-2">
          <span className="text-sm font-medium text-zinc-200 block font-sans">
            Initial Evaluation Phase — 0 Active Heuristics
          </span>
          <p className="text-xs font-mono text-zinc-400 max-w-lg mx-auto leading-relaxed">
            The inductive causal reflection engine triggers following weekly trade cycle settlements to extract candidate alpha rules and risk filters.
            All trade decisions currently adhere strictly to core persona tenets.
          </p>
        </div>
      )}
    </div>
  );
}
