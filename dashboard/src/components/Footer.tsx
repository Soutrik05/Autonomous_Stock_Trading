import { ShieldAlert, Terminal, Info } from 'lucide-react';

export default function Footer() {
  return (
    <footer className="border-t border-white/10 bg-[#090B10]/90 backdrop-blur-md py-10 text-slate-400 text-xs mt-20 font-sans">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-6">
        {/* Core Disclaimer Box - Translucent Glass Callout */}
        <div className="arena-glass p-5 flex flex-col md:flex-row items-start gap-4">
          <ShieldAlert className="w-5 h-5 text-blue-400 flex-shrink-0 mt-0.5" />
          <div className="space-y-1.5">
            <h4 className="font-bold text-white flex items-center gap-2 text-sm">
              <span>Academic Research & Paper-Trading Simulation Disclaimer</span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/30">
                Integer Paise Ledger
              </span>
            </h4>
            <p className="leading-relaxed text-xs text-slate-400">
              StockMinds is an academic evaluation experiment investigating whether LLM trading personas can trade Indian equities with prompt discipline, mathematical faithfulness, and measurable cognitive alpha over rules-only baselines and the Nifty 500 benchmark. <strong>All capital, positions, and orders are simulated paper trades denominated in integer paise</strong>. None of the signals, rationale, or outputs constitute financial advice, SEBI-registered research recommendations, or solicitations to buy or sell securities.
            </p>
          </div>
        </div>

        {/* System Meta & Architectural Guarantees */}
        <div className="flex flex-col sm:flex-row justify-between items-center gap-4 text-xs pt-4 border-t border-white/10">
          <div className="flex flex-wrap items-center gap-3 text-slate-500 font-mono">
            <span className="flex items-center gap-1.5">
              <Terminal className="w-3.5 h-3.5 text-slate-400" />
              <span>Branch: <code className="text-slate-300 font-medium">dashboard</code></span>
            </span>
            <span className="hidden md:inline text-white/10">|</span>
            <span>Accounting: <code className="text-slate-300">Integer Paise (Zero Floats)</code></span>
            <span className="hidden md:inline text-white/10">|</span>
            <span>Clock: <code className="text-slate-300">Asia/Kolkata (IST)</code></span>
            <span className="hidden md:inline text-white/10">|</span>
            <span>Significance Threshold: <code className="text-slate-300">N &ge; 30 trades</code></span>
          </div>

          <div className="flex items-center gap-2 text-slate-500 font-mono">
            <Info className="w-3.5 h-3.5 text-slate-400" />
            <span>StockMinds Autonomous Arena</span>
          </div>
        </div>
      </div>
    </footer>
  );
}
