import { ShieldAlert, Terminal, Info } from 'lucide-react';

export default function Footer() {
  return (
    <footer className="border-t border-[#DCD7CC] bg-[#F0EEE9] py-8 text-[#475060] text-xs mt-16 font-sans">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-6">
        {/* Core Disclaimer Box - Archival Callout Panel */}
        <div className="callout-panel p-4 flex flex-col md:flex-row items-start gap-3">
          <ShieldAlert className="w-4 h-4 text-[#8A7441] flex-shrink-0 mt-0.5" />
          <div className="space-y-1">
            <h4 className="font-serif font-semibold text-[#151B26] flex items-center gap-2 text-sm">
              <span>Academic research & paper-trading simulation disclaimer</span>
              <span className="text-[10px] font-mono px-1.5 py-0.2 rounded-[2px] bg-[#FFFFFF] text-[#8A7441] border border-[#D6C7A1]">
                Integer paise ledger
              </span>
            </h4>
            <p className="leading-relaxed text-[11px] text-[#475060]">
              StockMinds is an academic evaluation experiment investigating whether LLM trading personas can trade Indian equities with prompt discipline, mathematical faithfulness, and measurable cognitive alpha over rules-only baselines and the Nifty 500 benchmark. <strong>All capital, positions, and orders are simulated paper trades denominated in integer paise</strong>. None of the signals, rationale, or outputs constitute financial advice, SEBI-registered research recommendations, or solicitations to buy or sell securities.
            </p>
          </div>
        </div>

        {/* System Meta & Architectural Guarantees */}
        <div className="flex flex-col sm:flex-row justify-between items-center gap-3 text-[11px] pt-3 border-t border-[#DCD7CC]">
          <div className="flex flex-wrap items-center gap-3 text-[#7C8698] font-mono">
            <span className="flex items-center gap-1.5">
              <Terminal className="w-3.5 h-3.5 text-[#7C8698]" />
              <span>Branch: <code className="text-[#8A7441] font-medium">dashboard</code></span>
            </span>
            <span className="hidden md:inline text-[#DCD7CC]">|</span>
            <span>Accounting: <code className="text-[#151B26]">Integer paise (Zero floats)</code></span>
            <span className="hidden md:inline text-[#DCD7CC]">|</span>
            <span>Clock: <code className="text-[#151B26]">Asia/Kolkata (IST)</code></span>
            <span className="hidden md:inline text-[#DCD7CC]">|</span>
            <span>Significance threshold: <code className="text-[#151B26]">N &ge; 30 trades</code></span>
          </div>

          <div className="flex items-center gap-2 text-[#7C8698] font-mono">
            <Info className="w-3.5 h-3.5" />
            <span>StockMinds Autonomous Trading Arena</span>
          </div>
        </div>
      </div>
    </footer>
  );
}
