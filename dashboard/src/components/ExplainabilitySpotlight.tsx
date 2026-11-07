import { Brain, CheckCircle2, ShieldCheck, Quote } from 'lucide-react';

export default function ExplainabilitySpotlight() {
  const sampleDecision = {
    agentName: 'Peter Lynch',
    agentFamily: 'Growth at a Reasonable Price (GARP)',
    symbol: 'HBLENGINE',
    company: 'HBL Power Systems Ltd',
    action: 'BUY',
    rationale:
      'PEG of 0.65 qualifies as classic GARP candidate. ROCE of 28.4% and CFO/PAT conversion of 1.12 demonstrates real cash generation without accounting distortion. Sized conservatively with strict capital preservation.',
    citedMetrics: [
      { name: 'peg_ratio', cited: '0.65', snapshot: '0.65', tolerance: '±0.05', ok: true },
      { name: 'roce', cited: '28.4%', snapshot: '28.4%', tolerance: '±0.2%', ok: true },
      { name: 'cfo_to_pat', cited: '1.12', snapshot: '1.10', tolerance: '±0.05', ok: true },
    ],
  };

  return (
    <div className="arena-glass p-6 sm:p-8 space-y-5">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2 border-b border-white/10 pb-4">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-purple-500/10 border border-purple-500/30 flex items-center justify-center text-purple-400">
            <Brain className="w-4 h-4" />
          </div>
          <div>
            <h3 className="font-bold text-base sm:text-lg text-white">
              Explainability & Faithfulness Audit Spotlight
            </h3>
            <p className="text-xs text-slate-400">
              Every trade decision cites market metrics, checked deterministically against snapshot data.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 px-3 py-1 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-mono">
          <ShieldCheck className="w-3.5 h-3.5" />
          <span>Faithfulness: 100% Verified</span>
        </div>
      </div>

      {/* Verbatim Reasoning Card */}
      <div className="arena-glass-subdued p-5 rounded border border-white/10 relative space-y-2.5">
        <Quote className="w-6 h-6 text-slate-600/30 absolute top-4 right-4" />
        <div className="flex items-center gap-2 text-xs font-mono">
          <span className="font-bold text-white">{sampleDecision.agentName}</span>
          <span className="text-slate-600">·</span>
          <span className="text-slate-400">{sampleDecision.agentFamily}</span>
          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-blue-500/15 text-blue-300 border border-blue-500/30">
            BUY {sampleDecision.symbol}
          </span>
        </div>

        <p className="text-xs sm:text-sm text-slate-200 leading-relaxed italic pr-8">
          "{sampleDecision.rationale}"
        </p>
      </div>

      {/* Cited Metrics Grid */}
      <div>
        <div className="text-xs text-slate-400 mb-2 font-mono">
          Mathematical Ground-Truth Snapshot Verification:
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 text-xs font-mono">
          {sampleDecision.citedMetrics.map((cm, i) => (
            <div
              key={i}
              className="p-3 rounded-lg border border-white/10 bg-black/40 flex justify-between items-center"
            >
              <div>
                <span className="text-slate-500 block text-[11px]">{cm.name}</span>
                <span className="font-medium text-white">
                  Cited: {cm.cited} <span className="text-slate-500 font-normal">(Truth: {cm.snapshot})</span>
                </span>
              </div>
              <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
