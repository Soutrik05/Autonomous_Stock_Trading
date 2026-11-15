export default function Footer() {
  return (
    <footer className="border-t border-border-hairline bg-[#141414] text-zinc-400 font-sans mt-28 pt-12 pb-14">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">

        {/* Top Tier: Dominant Brand Masthead & Right-Aligned Fact Anchor */}
        <div className="flex flex-col md:flex-row md:items-start justify-between gap-8 pb-8 sm:pb-9">

          {/* Left Column: Wordmark & Narrative Tagline */}
          <div className="space-y-3 max-w-xl">
            <h2 className="font-display text-3xl sm:text-4xl font-semibold tracking-tight text-white">
              StockMinds
            </h2>
            <p className="text-base sm:text-lg text-zinc-200 font-sans leading-relaxed">
              A live experiment testing whether LLM judgment beats matched rules-based baselines on real Nifty 500 data.
            </p>
          </div>

          {/* Right Column: Status Badge & Compact Credibility Ledger */}
          <div className="flex flex-col md:items-end space-y-3 flex-shrink-0">
            <span className="inline-flex items-center gap-2 px-3 py-1 rounded text-xs font-mono font-medium border border-accent/40 text-accent bg-accent/10">
              <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
              Paper Trading Only
            </span>
            <div className="text-xs sm:text-[13px] font-mono text-zinc-400 space-y-1 md:text-right">
              <div>10 Agents · Live Since Nov 2026</div>
            </div>
          </div>

        </div>

        {/* Hairline Structural Divider */}
        <div className="border-t border-border-hairline" />

        {/* Bottom Tier: Compliance Statement & Colophon (Bumped Up) */}
        <div className="pt-6 space-y-4">
          <p className="text-sm sm:text-base text-zinc-300 font-sans leading-relaxed max-w-3xl">
            Research use only. All trades and portfolio values are simulated with paper capital. StockMinds is not registered with SEBI and does not provide investment advice.
          </p>

          <div className="flex flex-wrap items-center justify-between gap-y-2 text-xs sm:text-sm font-mono text-zinc-400 pt-1">
            <span>© 2026 StockMinds</span>
            <span>Built on NSE Nifty 500 · Live Data</span>
          </div>
        </div>

      </div>
    </footer>
  );
}
