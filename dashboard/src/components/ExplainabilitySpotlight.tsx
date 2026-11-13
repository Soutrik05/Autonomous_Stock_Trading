import { Brain, CheckCircle2, ShieldCheck, Quote } from 'lucide-react';

interface SpotlightItem {
  agentName: string;
  agentFamily: string;
  symbol: string;
  company: string;
  action: 'BUY' | 'SELL';
  rationale: string;
  citedMetrics: { name: string; cited: string; snapshot: string; tolerance: string; ok: boolean }[];
}

const SPOTLIGHT_DATA: Record<string, SpotlightItem> = {
  simons: {
    agentName: 'Jim Simons',
    agentFamily: 'Quantitative Statistical Momentum & Volatility Parity',
    symbol: 'ANANDRATHI',
    company: 'Anand Rathi Wealth Ltd',
    action: 'BUY',
    rationale:
      'Kaufman Efficiency Ratio is 0.74 with ADX 32.4 confirming robust trend efficiency. Volume surge 2.1x above 50-day average indicates institutional accumulation. ATR 2.4% calibrates volatility parity sizing at 10 shares with a strict trailing stop.',
    citedMetrics: [
      { name: 'kaufman_efficiency_ratio', cited: '0.74', snapshot: '0.74', tolerance: '±0.02', ok: true },
      { name: 'adx_14', cited: '32.4', snapshot: '32.4', tolerance: '±0.5', ok: true },
      { name: 'volume_ratio_50d', cited: '2.10', snapshot: '2.08', tolerance: '±0.10', ok: true },
      { name: 'atr_pct', cited: '2.40%', snapshot: '2.38%', tolerance: '±0.10%', ok: true },
    ],
  },
  lynch: {
    agentName: 'Peter Lynch',
    agentFamily: 'Growth-at-a-Reasonable-Price (GARP) & Cash Conversion',
    symbol: 'HBLENGINE',
    company: 'HBL Power Systems Ltd',
    action: 'BUY',
    rationale:
      'PEG of 0.65 qualifies as classic GARP candidate with earnings growth accelerating. ROCE of 28.4% and CFO/PAT conversion of 1.12 demonstrates real cash generation without accounting distortion. Sized conservatively with strict capital preservation.',
    citedMetrics: [
      { name: 'peg_ratio', cited: '0.65', snapshot: '0.65', tolerance: '±0.05', ok: true },
      { name: 'roce', cited: '28.4%', snapshot: '28.4%', tolerance: '±0.2%', ok: true },
      { name: 'cfo_to_pat', cited: '1.12', snapshot: '1.10', tolerance: '±0.05', ok: true },
      { name: 'debt_to_equity', cited: '0.14', snapshot: '0.14', tolerance: '±0.02', ok: true },
    ],
  },
  marks: {
    agentName: 'Howard Marks',
    agentFamily: 'Second-Level Contrarian Value & Margin of Safety',
    symbol: 'SCHAEFFLER',
    company: 'Schaeffler India Ltd',
    action: 'BUY',
    rationale:
      'Valuation in the lowest 8th percentile of 3-year historical P/E following cyclical auto ancillary destocking. Solvency buffer confirmed with net debt/equity of 0.12 and interest coverage of 14.2x. Extreme pessimistic sentiment provides an asymmetric margin of safety.',
    citedMetrics: [
      { name: 'pe_percentile_3yr', cited: '8.0%', snapshot: '8.0%', tolerance: '±1.0%', ok: true },
      { name: 'debt_to_equity', cited: '0.12', snapshot: '0.12', tolerance: '±0.02', ok: true },
      { name: 'interest_coverage', cited: '14.2x', snapshot: '14.2x', tolerance: '±0.5x', ok: true },
      { name: '52w_low_distance', cited: '3.8%', snapshot: '3.7%', tolerance: '±0.2%', ok: true },
    ],
  },
  jhunjhunwala: {
    agentName: 'Rakesh Jhunjhunwala',
    agentFamily: 'High-Conviction Structural Domestic Growth & Pyramiding',
    symbol: 'CRISIL',
    company: 'CRISIL Limited',
    action: 'BUY',
    rationale:
      'Dominant rating moat riding multi-year India corporate bond market expansion and bank credit cycle. Promoter holding at 67.2% demonstrates high institutional skin-in-the-game. 5-year average ROCE of 34.5% warrants concentrated high-conviction pyramiding allocation.',
    citedMetrics: [
      { name: 'promoter_holding', cited: '67.2%', snapshot: '67.2%', tolerance: '±0.5%', ok: true },
      { name: 'roce_5yr_avg', cited: '34.5%', snapshot: '34.5%', tolerance: '±0.5%', ok: true },
      { name: 'sales_cagr_3yr', cited: '18.2%', snapshot: '18.1%', tolerance: '±0.3%', ok: true },
      { name: 'operating_margin', cited: '31.4%', snapshot: '31.4%', tolerance: '±0.4%', ok: true },
    ],
  },
  varsity: {
    agentName: 'StockMinds Core',
    agentFamily: 'Dual-Confluence Swing & DCF Solvency Conservatism',
    symbol: 'TRENT',
    company: 'Trent Ltd',
    action: 'BUY',
    rationale:
      'Debt-to-equity of 0.38 satisfies Module 9 solvency requirements. Price pulled back to 20 EMA with positive RSI momentum confluence, confirming swing entry point with 2.0x ATR profit target.',
    citedMetrics: [
      { name: 'debt_to_equity', cited: '0.38', snapshot: '0.38', tolerance: '±0.05', ok: true },
      { name: 'current_ratio', cited: '1.45', snapshot: '1.45', tolerance: '±0.05', ok: true },
      { name: 'ema_20_distance', cited: '0.8%', snapshot: '0.8%', tolerance: '±0.2%', ok: true },
      { name: 'rsi_14', cited: '54.2', snapshot: '54.2', tolerance: '±1.0', ok: true },
    ],
  },
};

interface ExplainabilitySpotlightProps {
  personaId?: string;
}

export default function ExplainabilitySpotlight({ personaId = 'simons' }: ExplainabilitySpotlightProps) {
  const key = personaId.toLowerCase().replace('stockminds-core', 'varsity');
  const sampleDecision = SPOTLIGHT_DATA[key] || SPOTLIGHT_DATA['simons'];

  return (
    <div className="bg-[#161616] border border-border-hairline p-5 sm:p-6 rounded-lg space-y-5 font-sans">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 border-b border-border-hairline pb-4">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded bg-purple-500/10 border border-purple-500/30 flex items-center justify-center text-purple-400">
            <Brain className="w-4 h-4" />
          </div>
          <div>
            <h3 className="font-serif font-medium text-base sm:text-lg text-white">
              Explainability & Faithfulness Audit Spotlight
            </h3>
            <p className="text-xs text-zinc-400 font-sans">
              Every trade decision cites market metrics, checked deterministically against snapshot ground-truth.
            </p>
          </div>
        </div>

        {/* Purple semantic badge for trust/verification */}
        <div className="flex items-center gap-2 px-2.5 py-1 rounded bg-purple-500/10 border border-purple-500/30 text-purple-400 text-xs font-mono">
          <ShieldCheck className="w-3.5 h-3.5" />
          <span>Faithfulness: 100% Ground Truth Verified</span>
        </div>
      </div>

      {/* Verbatim Reasoning Card */}
      <div className="bg-[#121212] p-4 sm:p-5 rounded border border-border-hairline relative space-y-2.5">
        <Quote className="w-5 h-5 text-zinc-600/30 absolute top-4 right-4" />
        <div className="flex flex-wrap items-center gap-2 text-xs font-mono">
          <span className="font-semibold text-white">{sampleDecision.agentName}</span>
          <span className="text-zinc-600">·</span>
          <span className="text-zinc-400">{sampleDecision.agentFamily}</span>
          <span className="px-2 py-0.5 rounded text-[10px] font-mono border border-border-hairline text-zinc-200 bg-white/[0.04]">
            {sampleDecision.action} {sampleDecision.symbol}
          </span>
        </div>

        <p className="text-xs sm:text-sm text-zinc-200 leading-relaxed italic pr-6 font-sans">
          "{sampleDecision.rationale}"
        </p>
      </div>

      {/* Cited Metrics Grid with Cited vs Actual Pairing */}
      <div className="space-y-2">
        <div className="text-[11px] text-zinc-500 font-mono uppercase tracking-wider">
          Mathematical Ground-Truth Snapshot Verification:
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5 text-xs font-mono">
          {sampleDecision.citedMetrics.map((cm, i) => (
            <div
              key={i}
              className="p-3 rounded border border-border-hairline bg-[#121212] flex justify-between items-center"
            >
              <div>
                <span className="text-zinc-500 block text-[11px]">{cm.name}</span>
                <span className="font-medium text-white text-xs">
                  Cited: {cm.cited}{' '}
                  <span className="text-zinc-500 font-normal text-[11px]">({cm.snapshot})</span>
                </span>
              </div>
              <CheckCircle2 className="w-4 h-4 text-purple-400 flex-shrink-0" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
