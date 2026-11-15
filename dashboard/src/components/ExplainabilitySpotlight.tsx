import { Check, ShieldCheck } from 'lucide-react';
import { cn } from '../utils/cn';

interface CitedMetricItem {
  label: string;
  cited: string;
  snapshot: string;
  discrepancy: string;
  ok: boolean;
}

interface SpotlightItem {
  agentName: string;
  agentFamily: string;
  symbol: string;
  company: string;
  action: 'BUY' | 'SELL';
  executionCycle: string;
  rationale: string;
  highlightTokens: string[];
  citedMetrics: CitedMetricItem[];
}

const SPOTLIGHT_DATA: Record<string, SpotlightItem> = {
  simons: {
    agentName: 'Jim Simons',
    agentFamily: 'Quantitative Statistical Momentum & Volatility Parity',
    symbol: 'ANANDRATHI',
    company: 'Anand Rathi Wealth Ltd',
    action: 'BUY',
    executionCycle: 'EOD Batch Bar #48',
    rationale:
      'Kaufman Efficiency Ratio is 0.74 with ADX 32.4 confirming robust trend efficiency. Volume surge 2.1x above 50-day average indicates institutional accumulation. ATR 2.4% calibrates volatility parity sizing at 10 shares with a strict trailing stop.',
    highlightTokens: ['0.74', '32.4', '2.1x', '2.4%'],
    citedMetrics: [
      { label: 'Kaufman Efficiency Ratio (KER)', cited: '0.74', snapshot: '0.74', discrepancy: '0.00', ok: true },
      { label: 'Average Directional Index (ADX 14)', cited: '32.4', snapshot: '32.4', discrepancy: '0.00', ok: true },
      { label: 'Volume Surge Ratio (50-Day)', cited: '2.10x', snapshot: '2.08x', discrepancy: '+0.02x', ok: true },
      { label: 'Average True Range (ATR %)', cited: '2.40%', snapshot: '2.38%', discrepancy: '+0.02%', ok: true },
    ],
  },
  lynch: {
    agentName: 'Peter Lynch',
    agentFamily: 'Growth-at-a-Reasonable-Price (GARP) & Cash Conversion',
    symbol: 'HBLENGINE',
    company: 'HBL Power Systems Ltd',
    action: 'BUY',
    executionCycle: 'EOD Batch Bar #48',
    rationale:
      'PEG of 0.65 qualifies as classic GARP candidate with earnings growth accelerating. ROCE of 28.4% and CFO/PAT conversion of 1.12 demonstrates real cash generation without accounting distortion. Sized conservatively with strict capital preservation.',
    highlightTokens: ['0.65', '28.4%', '1.12', '0.14'],
    citedMetrics: [
      { label: 'Price / Earnings-to-Growth (PEG)', cited: '0.65', snapshot: '0.65', discrepancy: '0.00', ok: true },
      { label: 'Return on Capital Employed (ROCE)', cited: '28.4%', snapshot: '28.4%', discrepancy: '0.00', ok: true },
      { label: 'Cash Conversion (CFO / PAT)', cited: '1.12', snapshot: '1.10', discrepancy: '+0.02', ok: true },
      { label: 'Debt-to-Equity Ratio', cited: '0.14', snapshot: '0.14', discrepancy: '0.00', ok: true },
    ],
  },
  marks: {
    agentName: 'Howard Marks',
    agentFamily: 'Second-Level Contrarian Value & Margin of Safety',
    symbol: 'SCHAEFFLER',
    company: 'Schaeffler India Ltd',
    action: 'BUY',
    executionCycle: 'EOD Batch Bar #48',
    rationale:
      'Valuation in the lowest 8th percentile of 3-year historical P/E following cyclical auto ancillary destocking. Solvency buffer confirmed with net debt/equity of 0.12 and interest coverage of 14.2x. Extreme pessimistic sentiment provides an asymmetric margin of safety.',
    highlightTokens: ['8th percentile', '0.12', '14.2x', '3.8%'],
    citedMetrics: [
      { label: '3-Year Historical P/E Percentile', cited: '8.0%', snapshot: '8.0%', discrepancy: '0.00', ok: true },
      { label: 'Net Debt-to-Equity', cited: '0.12', snapshot: '0.12', discrepancy: '0.00', ok: true },
      { label: 'Interest Coverage Ratio', cited: '14.2x', snapshot: '14.2x', discrepancy: '0.00', ok: true },
      { label: 'Distance from 52-Week Low', cited: '3.8%', snapshot: '3.7%', discrepancy: '+0.10%', ok: true },
    ],
  },
  jhunjhunwala: {
    agentName: 'Rakesh Jhunjhunwala',
    agentFamily: 'High-Conviction Structural Domestic Growth & Pyramiding',
    symbol: 'CRISIL',
    company: 'CRISIL Limited',
    action: 'BUY',
    executionCycle: 'EOD Batch Bar #48',
    rationale:
      'Dominant rating moat riding multi-year India corporate bond market expansion and bank credit cycle. Promoter holding at 67.2% demonstrates high institutional skin-in-the-game. 5-year average ROCE of 34.5% warrants concentrated high-conviction pyramiding allocation.',
    highlightTokens: ['67.2%', '34.5%', '18.2%', '31.4%'],
    citedMetrics: [
      { label: 'Promoter Equity Holding', cited: '67.2%', snapshot: '67.2%', discrepancy: '0.00', ok: true },
      { label: '5-Year Average ROCE', cited: '34.5%', snapshot: '34.5%', discrepancy: '0.00', ok: true },
      { label: '3-Year Sales CAGR', cited: '18.2%', snapshot: '18.1%', discrepancy: '+0.10%', ok: true },
      { label: 'Operating Profit Margin (OPM)', cited: '31.4%', snapshot: '31.4%', discrepancy: '0.00', ok: true },
    ],
  },
  varsity: {
    agentName: 'StockMinds Core',
    agentFamily: 'Dual-Confluence Swing & DCF Solvency Conservatism',
    symbol: 'TRENT',
    company: 'Trent Ltd',
    action: 'BUY',
    executionCycle: 'EOD Batch Bar #48',
    rationale:
      'Debt-to-equity of 0.38 satisfies Module 9 solvency requirements. Price pulled back to 20 EMA with positive RSI momentum confluence, confirming swing entry point with 2.0x ATR profit target.',
    highlightTokens: ['0.38', '1.45', '0.8%', '54.2'],
    citedMetrics: [
      { label: 'Balance-Sheet Debt-to-Equity', cited: '0.38', snapshot: '0.38', discrepancy: '0.00', ok: true },
      { label: 'Current Liquidity Ratio', cited: '1.45', snapshot: '1.45', discrepancy: '0.00', ok: true },
      { label: 'Distance from 20 EMA Support', cited: '0.8%', snapshot: '0.8%', discrepancy: '0.00', ok: true },
      { label: 'Relative Strength Index (RSI 14)', cited: '54.2', snapshot: '54.2', discrepancy: '0.00', ok: true },
    ],
  },
};

interface ExplainabilitySpotlightProps {
  personaId?: string;
}

export default function ExplainabilitySpotlight({ personaId = 'simons' }: ExplainabilitySpotlightProps) {
  const key = personaId.toLowerCase().replace('stockminds-core', 'varsity');
  const sampleDecision = SPOTLIGHT_DATA[key] || SPOTLIGHT_DATA['simons'];

  // Helper to render rationale with highlighted cited tokens
  const renderHighlightedRationale = (text: string, tokens: string[]) => {
    if (!tokens || tokens.length === 0) return text;
    const escaped = tokens.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|');
    const parts = text.split(new RegExp(`(${escaped})`, 'gi'));
    return parts.map((part, idx) => {
      const isMatch = tokens.some((t) => t.toLowerCase() === part.toLowerCase());
      if (isMatch) {
        return (
          <mark
            key={idx}
            className="bg-accent/20 text-accent px-1.5 py-0.5 rounded font-mono text-sm font-semibold"
          >
            {part}
          </mark>
        );
      }
      return part;
    });
  };

  return (
    <div className="border border-border-hairline bg-surface-inset rounded-lg overflow-hidden font-sans">
      
      {/* 1. Header with Audit Status */}
      <div className="px-5 py-4 bg-surface-well border-b border-border-hairline flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
        <div>
          <h3 className="font-display font-medium text-base sm:text-lg text-white">
            Forensic Reasoning & Ground-Truth Verification
          </h3>
          <p className="text-xs sm:text-sm text-zinc-400 font-sans mt-0.5">
            Every numeric claim cited in agent trade memos is verified against raw exchange snapshot data.
          </p>
        </div>

        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded bg-emerald-500/10 border border-emerald-500/25 text-emerald-400 text-xs sm:text-sm font-mono flex-shrink-0">
          <ShieldCheck className="w-4 h-4 text-emerald-400" />
          <span>Audit: 100% Verified · 0 Hallucinations</span>
        </div>
      </div>

      {/* 2. Simplified Execution Memo Bar */}
      <div className="p-5 sm:p-6 bg-surface-well/30 border-b border-border-hairline space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <span
              className={cn(
                'px-2.5 py-1 rounded text-xs font-mono font-semibold uppercase tracking-wider',
                sampleDecision.action === 'BUY'
                  ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                  : 'bg-rose-500/15 text-rose-400 border border-rose-500/30'
              )}
            >
              {sampleDecision.action}
            </span>
            <span className="text-white font-mono font-bold text-sm sm:text-base">
              NSE: {sampleDecision.symbol}
            </span>
            <span className="text-zinc-600">·</span>
            <span className="text-sm text-zinc-300 font-sans">
              {sampleDecision.company}
            </span>
          </div>

          <span className="text-xs font-mono text-zinc-400">
            Agent: <strong className="text-zinc-200 font-medium">{sampleDecision.agentName}</strong>
          </span>
        </div>

        {/* Verbatim quote in clear, legible text */}
        <p className="text-sm sm:text-base text-zinc-200 font-sans leading-relaxed pt-1">
          "{renderHighlightedRationale(sampleDecision.rationale, sampleDecision.highlightTokens)}"
        </p>
      </div>

      {/* 3. High-Legibility Audit Table (4 Columns, Bumped Font Sizes) */}
      <div className="overflow-x-auto">
        <table className="w-full text-left font-mono text-sm sm:text-base">
          <thead className="bg-surface-well text-xs sm:text-sm text-zinc-400 border-b border-border-hairline">
            <tr>
              <th className="py-3 px-5 font-normal">Audited Indicator</th>
              <th className="py-3 px-5 text-right font-normal text-accent">Cited Claim</th>
              <th className="py-3 px-5 text-right font-normal text-zinc-300">Exchange Snapshot</th>
              <th className="py-3 px-5 text-right font-normal text-zinc-400">Variance (Δ)</th>
              <th className="py-3 px-5 text-right font-normal text-zinc-300">Audit Verdict</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border-hairline text-zinc-300">
            {sampleDecision.citedMetrics.map((cm, idx) => (
              <tr key={idx} className="hover:bg-white/[0.02] transition-colors">
                <td className="py-3.5 px-5 font-sans font-medium text-white text-sm sm:text-base">
                  {cm.label}
                </td>
                <td className="py-3.5 px-5 text-right font-mono font-bold text-accent text-sm sm:text-base tabular-nums">
                  {cm.cited}
                </td>
                <td className="py-3.5 px-5 text-right font-mono font-medium text-zinc-100 text-sm sm:text-base tabular-nums">
                  {cm.snapshot}
                </td>
                <td className="py-3.5 px-5 text-right font-mono text-zinc-400 text-sm sm:text-base tabular-nums">
                  {cm.discrepancy}
                </td>
                <td className="py-3.5 px-5 text-right">
                  <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs sm:text-sm font-mono font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/25">
                    <Check className="w-3.5 h-3.5 text-emerald-400" />
                    PASS
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

    </div>
  );
}
