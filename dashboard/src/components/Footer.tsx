import { ShieldAlert, Terminal, Info } from 'lucide-react';

export default function Footer() {
  return (
    <footer className="border-t border-[#E5E2D9] bg-[#FAF9F6] py-10 text-[#4B5563] text-xs mt-16 font-sans">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-6">
        {/* Core Disclaimer Box */}
        <div className="p-4 rounded-xl border border-amber-200/80 bg-amber-50/40 text-amber-950 flex flex-col md:flex-row items-start gap-3">
          <ShieldAlert className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
          <div className="space-y-1">
            <h4 className="font-serif font-bold text-amber-950 flex items-center gap-2">
              <span>Academic Research & Paper-Trading Simulation Disclaimer</span>
              <span className="text-[9px] font-mono uppercase bg-amber-200/60 px-1.5 py-0.5 rounded text-amber-900 border border-amber-300/60 font-semibold">
                Simulated Execution · Integer Paise Ledger
              </span>
            </h4>
            <p className="leading-relaxed text-[11px] text-amber-900/80">
              StockMinds is an academic evaluation experiment investigating whether LLM trading personas can trade Indian equities with prompt discipline, mathematical faithfulness, and measurable cognitive alpha over rules-only baselines and the Nifty 500 benchmark. <strong>All capital, positions, and orders are simulated paper trades denominated in integer paise</strong>. None of the signals, rationale, or outputs constitute financial advice, SEBI-registered research recommendations, or solicitations to buy or sell securities.
            </p>
          </div>
        </div>

        {/* System Meta & Architectural Guarantees */}
        <div className="flex flex-col sm:flex-row justify-between items-center gap-4 text-[11px] pt-3 border-t border-[#EDEAE2]">
          <div className="flex flex-wrap items-center gap-4 text-[#9CA3AF] font-mono">
            <span className="flex items-center gap-1.5">
              <Terminal className="w-3.5 h-3.5 text-stone-400" />
              <span>Branch: <code className="text-amber-700 font-semibold">dashboard</code> (base: <code className="text-stone-700">v2-ATA</code>)</span>
            </span>
            <span className="hidden md:inline">·</span>
            <span>Accounting: <code className="text-stone-700">Integer Paise (Zero Floats)</code></span>
            <span className="hidden md:inline">·</span>
            <span>Clock: <code className="text-stone-700">IST (Asia/Kolkata)</code></span>
            <span className="hidden md:inline">·</span>
            <span>Small-Sample Threshold: <code className="text-stone-700">N &ge; 30 trades</code></span>
          </div>

          <div className="flex items-center gap-2 text-[#9CA3AF] font-mono">
            <Info className="w-3.5 h-3.5" />
            <span>StockMinds Autonomous Multi-Agent Platform</span>
          </div>
        </div>
      </div>
    </footer>
  );
}
