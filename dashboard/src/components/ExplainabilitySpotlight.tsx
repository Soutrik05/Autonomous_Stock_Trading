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
    <div className="ledger-panel p-6 space-y-4">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2 border-b border-[#E7E3D9] pb-3">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-[3px] bg-[#EDF2F9] flex items-center justify-center text-[#2A4B7C] border border-[#B9C9E1]">
            <Brain className="w-4 h-4" />
          </div>
          <div>
            <h3 className="font-serif font-bold text-base text-[#151B26]">
              Explainability & faithfulness audit spotlight
            </h3>
            <p className="text-[11px] font-sans text-[#7C8698]">
              Every trade decision cites market metrics, checked deterministically against snapshot data.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-[2px] bg-[#EBF5F0] border border-[#A3D4BE] text-[#1E6548] text-xs font-mono">
          <ShieldCheck className="w-3.5 h-3.5" />
          <span>Faithfulness: 100% verified</span>
        </div>
      </div>

      {/* Verbatim Reasoning Card */}
      <div className="callout-panel p-4 relative space-y-2">
        <Quote className="w-5 h-5 text-[#8A7441]/40 absolute top-3 right-3" />
        <div className="flex items-center gap-2 text-xs font-mono">
          <span className="font-semibold text-[#151B26]">{sampleDecision.agentName}</span>
          <span className="text-[#7C8698]">·</span>
          <span className="text-[#475060]">{sampleDecision.agentFamily}</span>
          <span className="px-1.5 py-0.2 rounded-[2px] text-[10px] font-semibold bg-[#EBF5F0] text-[#1E6548] border border-[#A3D4BE]">
            BUY {sampleDecision.symbol}
          </span>
        </div>

        <p className="text-xs text-[#151B26] font-serif leading-relaxed italic pr-6">
          "{sampleDecision.rationale}"
        </p>
      </div>

      {/* Cited Metrics Grid */}
      <div>
        <div className="text-[11px] font-sans text-[#7C8698] mb-2">
          Mathematical ground-truth snapshot verification:
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs font-mono">
          {sampleDecision.citedMetrics.map((cm, i) => (
            <div
              key={i}
              className="p-2.5 rounded-[2px] border border-[#DCD7CC] bg-[#FFFFFF] flex justify-between items-center"
            >
              <div>
                <span className="text-[#475060] block text-[11px]">{cm.name}</span>
                <span className="font-medium text-[#151B26]">
                  Cited: {cm.cited} <span className="text-[#7C8698] font-normal">(Truth: {cm.snapshot})</span>
                </span>
              </div>
              <CheckCircle2 className="w-4 h-4 text-[#1E6548] flex-shrink-0" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
