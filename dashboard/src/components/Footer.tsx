import { Link } from 'react-router-dom';

export default function Footer() {
  return (
    <footer className="border-t border-white/[0.08] bg-[#0A0A0B] text-zinc-400 font-sans mt-28 pt-12 pb-14">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-10">

        {/* Top Grid: Masthead & Navigation */}
        <div className="grid grid-cols-1 md:grid-cols-12 gap-10 items-start">

          {/* Col 1: Wordmark & Core Mandate */}
          <div className="md:col-span-7 space-y-3">
            <div className="flex items-center gap-2">
              <span className="font-serif text-2xl font-normal text-white tracking-tight">StockMinds Benchmark</span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded border border-[#D4AF37]/30 text-[#D4AF37] bg-[#D4AF37]/5">
                NIFTY 500
              </span>
            </div>
            <p className="text-xs text-zinc-400 leading-relaxed font-sans max-w-lg">
              An empirical benchmark testing whether LLM judgment adds measurable value over matched rules-based baselines — tracked, scored, and shown in full.
            </p>
            <div className="text-[11px] font-mono text-zinc-500 pt-1">
              Zero-float integer paise accounting · Complete execution audit trail
            </div>
          </div>

          {/* Col 2: Navigation Links */}
          <div className="md:col-span-5 space-y-3">
            <div className="text-[10px] font-mono uppercase tracking-widest text-zinc-500">
              Benchmark Navigation
            </div>
            <div className="grid grid-cols-2 gap-2 text-xs font-mono">
              <Link to="/" className="text-zinc-400 hover:text-white transition-colors">Overview</Link>
              <Link to="/leaderboard" className="text-zinc-400 hover:text-white transition-colors">Current Standings (10 Strategies)</Link>
              <Link to="/portfolio/simons" className="text-zinc-400 hover:text-white transition-colors">Strategy Dossiers & Blotter</Link>
              <Link to="/comparison" className="text-zinc-400 hover:text-white transition-colors">LLM vs Rules Comparisons</Link>
              <Link to="/backtest" className="text-zinc-400 hover:text-white transition-colors">Walk-Forward Backtest Lab</Link>
              <Link to="/pulse" className="text-zinc-400 hover:text-white transition-colors">Telemetry Pulse</Link>
            </div>
          </div>

        </div>

        {/* Bottom Cardless Advisory & Copyright */}
        <div className="border-t border-white/[0.08] pt-6 space-y-3">
          <div className="flex items-center justify-between text-[10px] font-mono uppercase tracking-widest text-zinc-500">
            <span>Research Disclaimer</span>
            <span className="text-amber-400/90 font-medium">Paper Trading Only</span>
          </div>
          <p className="text-xs text-zinc-500 leading-relaxed font-sans max-w-3xl">
            StockMinds is an academic research platform for empirical market evaluation. All trades, orders, and portfolio NAVs are strictly simulated. Not registered with SEBI; does not offer financial or investment advice.
          </p>
          <div className="pt-2 flex flex-wrap justify-between items-center text-[10px] font-mono text-zinc-600">
            <span>StockMinds Benchmark © 2026 · Built for NSE Nifty 500 Benchmark</span>
            <span>All costs and charges accounted in integer paise</span>
          </div>
        </div>

      </div>
    </footer>
  );
}
