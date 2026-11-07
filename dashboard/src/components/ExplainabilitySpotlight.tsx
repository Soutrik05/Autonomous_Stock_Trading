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
    <div className="porcelain-card p-6 space-y-4">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2 border-b border-[#E5E2D9] pb-3">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-purple-100 flex items-center justify-center text-purple-700">
            <Brain className="w-4 h-4" />
          </div>
          <div>
            <h3 className="font-serif font-bold text-base text-[#111827]">
              Explainability & Faithfulness Audit Spotlight
            </h3>
            <p className="text-[11px] font-mono text-[#4B5563]">
              Every trade decision cites market metrics, checked deterministically against snapshot data.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-purple-50 border border-purple-200 text-purple-800 text-xs font-mono">
          <ShieldCheck className="w-3.5 h-3.5" />
          <span>Faithfulness: 100% Verified</span>
        </div>
      </div>

      {/* Verbatim Reasoning Card */}
      <div className="p-4 rounded-xl bg-[#F4F2EC] border border-[#E5E2D9] relative space-y-2">
        <Quote className="w-6 h-6 text-amber-500/30 absolute top-3 right-3" />
        <div className="flex items-center gap-2 text-xs font-mono">
          <span className="font-bold text-[#111827]">{sampleDecision.agentName}</span>
          <span className="text-[#9CA3AF]">·</span>
          <span className="text-[#4B5563]">{sampleDecision.agentFamily}</span>
          <span className="px-1.5 py-0.2 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800">
            BUY {sampleDecision.symbol}
          </span>
        </div>

        <p className="text-xs text-[#111827] font-sans leading-relaxed italic pr-6">
          "{sampleDecision.rationale}"
        </p>
      </div>

      {/* Cited Metrics Grid */}
      <div>
        <div className="text-[10px] font-mono uppercase text-[#9CA3AF] mb-2 tracking-wider">
          Mathematical Ground-Truth Snapshot Verification:
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs font-mono">
          {sampleDecision.citedMetrics.map((cm, i) => (
            <div
              key={i}
              className="p-2.5 rounded-lg border border-[#E5E2D9] bg-white flex justify-between items-center"
            >
              <div>
                <span className="text-[#4B5563] block text-[11px]">{cm.name}</span>
                <span className="font-bold text-[#111827]">
                  Cited: {cm.cited} <span className="text-[#9CA3AF] font-normal">(Truth: {cm.snapshot})</span>
                </span>
              </div>
              <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
