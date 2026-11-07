import { Link } from 'react-router-dom';

export default function Footer() {
  return (
    <footer className="border-t border-white/[0.08] bg-black text-zinc-400 font-sans mt-24 pt-12 pb-16">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-10">
        
        {/* Top Brand & Navigation Grid */}
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
          <div className="space-y-1">
            <span className="font-serif text-lg text-white tracking-tight">StockMinds Arena</span>
            <p className="text-xs font-mono text-zinc-500">
              Autonomous Multi-Agent Paper-Trading Evaluation · NSE Nifty 500
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-6 font-mono text-xs">
            <Link to="/" className="text-zinc-400 hover:text-white transition-colors">Overview</Link>
            <Link to="/leaderboard" className="text-zinc-400 hover:text-white transition-colors">Leaderboard</Link>
            <Link to="/comparison" className="text-zinc-400 hover:text-white transition-colors">Comparison</Link>
            <Link to="/backtest" className="text-zinc-400 hover:text-white transition-colors">Backtest Lab</Link>
            <Link to="/pulse" className="text-zinc-400 hover:text-white transition-colors">Telemetry Pulse</Link>
          </div>
        </div>

        {/* Standard Trading & Research Advisory */}
        <div className="pt-8 border-t border-white/[0.06] space-y-3">
          <div className="text-[10px] font-mono uppercase tracking-widest text-zinc-500">
            Advisory & Regulatory Disclosure
          </div>
          <p className="text-xs text-zinc-500 leading-relaxed font-sans max-w-4xl">
            StockMinds is an academic research experiment evaluating autonomous agent behavior, decision explainability, and cognitive edge. All portfolios, orders, and execution ledgers are simulated paper-trading records denominated in integer paise. This platform does not provide financial advice, SEBI-registered investment recommendations, portfolio management services, or solicitations to buy or sell securities. Simulated performance and backtested models do not guarantee real-market returns. Use at your own risk.
          </p>
          <div className="text-[11px] font-mono text-zinc-600 pt-2 flex flex-wrap gap-4">
            <span>© 2026 StockMinds Project</span>
            <span>·</span>
            <span>Zero-Float Integer Paise Ledger</span>
            <span>·</span>
            <span>Deterministic Faithfulness Verified</span>
          </div>
        </div>

      </div>
    </footer>
  );
}
