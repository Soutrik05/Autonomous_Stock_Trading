import type { HeuristicMemory } from '../types';
import { Layers } from 'lucide-react';

interface LearnedMemoryBankSectionProps {
  heuristics: HeuristicMemory[];
}

export default function LearnedMemoryBankSection({ heuristics }: LearnedMemoryBankSectionProps) {
  return (
    <section className="space-y-4 font-sans">
      {/* Section Header (Cardless Monograph Header) */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2 border-b border-white/[0.08] pb-3">
        <div>
          <h2 className="font-display text-xl sm:text-2xl font-normal tracking-tight text-white flex items-center gap-2.5">
            <Layers className="w-4 h-4 text-[#D4AF37]" />
            <span>Learned Memory Bank</span>
            <span className="text-xs font-mono px-2 py-0.5 rounded bg-white/[0.04] text-zinc-300 border border-white/10 font-normal">
              {heuristics.length} {heuristics.length === 1 ? 'Rule' : 'Rules'} Active
            </span>
          </h2>
          <p className="text-xs font-mono text-zinc-400 mt-0.5">
            Causal heuristics extracted from closed trade post-mortems via weekly reflection
          </p>
        </div>
      </div>

      {/* Heuristic Rules Ledger (Clean, Non-Cluttered, High Legibility) */}
      {heuristics.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {heuristics.map((h) => {
            const isSeek = h.kind === 'SEEK';

            return (
              <div
                key={h.id}
                className="bg-white/[0.02] border border-white/[0.08] hover:border-white/20 transition-all p-5 rounded-sm space-y-3.5 flex flex-col justify-between"
              >
                <div className="space-y-3">
                  {/* Top Meta Strip: Category Classification & Verification State */}
                  <div className="flex items-center justify-between text-xs font-mono">
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-mono tracking-wider font-medium border ${
                        isSeek
                          ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/25'
                          : 'bg-rose-500/10 text-rose-400 border-rose-500/25'
                      }`}
                    >
                      {isSeek ? 'ALPHA RULE' : 'RISK FILTER'}
                    </span>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-white/[0.04] text-zinc-400 border border-white/10">
                      STATUS: {h.status}
                    </span>
                  </div>

                  {/* Core Heuristic Thesis (High Legibility Editorial Prose) */}
                  <p className="text-sm sm:text-[15px] font-sans font-normal text-white leading-relaxed">
                    {h.ruleDescription}
                  </p>

                  {/* Trigger Predicate (Clean Inline Expression) */}
                  {h.triggerPredicate && (
                    <div className="text-xs font-mono text-zinc-300 bg-white/[0.02] border-l-2 border-white/20 pl-3 py-1.5 space-y-0.5">
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
                <div className="flex items-center justify-between text-xs font-mono text-zinc-400 pt-3 border-t border-white/[0.06]">
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
        /* Clean Monograph State when 0 heuristics in early pilot */
        <div className="p-8 text-center bg-white/[0.01] border border-white/[0.08] rounded-sm space-y-2">
          <span className="text-sm font-medium text-zinc-200 block font-sans">
            Initial Evaluation Phase — 0 Active Heuristics
          </span>
          <p className="text-xs font-mono text-zinc-400 max-w-lg mx-auto leading-relaxed">
            The inductive causal reflection engine triggers following weekly trade cycle settlements to extract candidate alpha rules and risk filters.
            All trade decisions currently adhere strictly to core persona tenets.
          </p>
        </div>
      )}
    </section>
  );
}
