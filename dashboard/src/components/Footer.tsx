import { ShieldAlert, Terminal, Info } from 'lucide-react';

export default function Footer() {
  return (
    <footer className="border-t border-stone-200 dark:border-stone-800 bg-stone-50 dark:bg-stone-950 py-8 text-stone-500 dark:text-stone-400 text-xs mt-12">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-6">
        {/* Core Disclaimer Box */}
        <div className="p-4 rounded-xl border border-amber-200 dark:border-amber-900/50 bg-amber-50/60 dark:bg-amber-950/20 text-amber-900 dark:text-amber-200/90 flex flex-col md:flex-row items-start gap-3">
          <ShieldAlert className="w-5 h-5 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" />
          <div className="space-y-1">
            <h4 className="font-semibold text-amber-950 dark:text-amber-100 flex items-center gap-2">
              <span>Academic Research & Paper-Trading Simulation Disclaimer</span>
              <span className="text-[10px] font-mono uppercase bg-amber-200 dark:bg-amber-900/60 px-1.5 py-0.5 rounded text-amber-900 dark:text-amber-200">
                Non-Commercial · Simulated Execution
              </span>
            </h4>
            <p className="leading-relaxed text-[11px] text-amber-900/80 dark:text-amber-300/80">
              StockMinds is an academic evaluation experiment studying whether LLM trading personas (Simons, Lynch, Marks, Jhunjhunwala, Varsity) can trade Indian equities with explainability, prompt discipline, and verifiable value-add over a rules-only control baseline. <strong>All capital, positions, and orders are purely simulated paper-trades denominated in integer paise</strong>. None of the signals, rationale, or outputs constitute financial advice, SEBI-registered research recommendations, or solicitations to buy or sell securities.
            </p>
          </div>
        </div>

        {/* System Meta & Architectural Guarantees */}
        <div className="flex flex-col sm:flex-row justify-between items-center gap-4 text-[11px] pt-2 border-t border-stone-200/60 dark:border-stone-800/60">
          <div className="flex flex-wrap items-center gap-4 text-stone-500 font-mono">
            <span className="flex items-center gap-1">
              <Terminal className="w-3.5 h-3.5 text-stone-400" />
              <span>Branch: <code className="text-amber-600 dark:text-amber-400">dashboard</code> (base: <code className="text-stone-700 dark:text-stone-300">v2-ATA</code>)</span>
            </span>
            <span className="hidden md:inline">·</span>
            <span>Ledger: <code className="text-stone-700 dark:text-stone-300">Integer Paise Accounting</code></span>
            <span className="hidden md:inline">·</span>
            <span>Clock: <code className="text-stone-700 dark:text-stone-300">IST (Asia/Kolkata)</code></span>
            <span className="hidden md:inline">·</span>
            <span>Small-sample threshold: <code className="text-stone-700 dark:text-stone-300">N &ge; 30 trades</code></span>
          </div>

          <div className="flex items-center gap-2 text-stone-400 font-mono">
            <Info className="w-3.5 h-3.5" />
            <span>StockMinds Week 5 Frontend Architecture</span>
          </div>
        </div>
      </div>
    </footer>
  );
}
