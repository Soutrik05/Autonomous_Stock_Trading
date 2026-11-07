import { useState } from 'react';
import { Filter, ChevronRight } from 'lucide-react';

interface FunnelStage {
  step: number;
  name: string;
  count: number;
  subtitle: string;
  criteria: string;
  droppedCount: number;
  sampleDropped: { symbol: string; reason: string }[];
}

const FUNNEL_DATA_BY_PERSONA: Record<string, { personaName: string; stages: FunnelStage[] }> = {
  simons: {
    personaName: 'Jim Simons (Quant Momentum)',
    stages: [
      {
        step: 0,
        name: 'Universe Ingestion',
        count: 500,
        subtitle: 'NSE Nifty 500 constituents',
        criteria: 'Daily EOD OHLCV + technical indicators computed point-in-time',
        droppedCount: 0,
        sampleDropped: [],
      },
      {
        step: 1,
        name: 'Liquidity Filter',
        count: 348,
        subtitle: 'Stage-1 Volume & Price bounds',
        criteria: '20-day median turnover >= ₹5 Cr AND close >= ₹20',
        droppedCount: 152,
        sampleDropped: [
          { symbol: 'SUZLON', reason: 'Median turnover < ₹5 Cr threshold' },
          { symbol: 'IDEA', reason: 'Penny price boundary violated' },
        ],
      },
      {
        step: 2,
        name: 'Momentum Hurdles',
        count: 19,
        subtitle: 'Stage-2 Quantitative Signal',
        criteria: 'Kaufman ER > 0.60 AND ADX 14 >= 25 AND positive skew',
        droppedCount: 329,
        sampleDropped: [
          { symbol: 'RELIANCE', reason: 'Kaufman ER is 0.38 (below 0.60 hurdle - choppy regime)' },
          { symbol: 'TCS', reason: 'ADX is 18.2 (insufficient trend strength)' },
        ],
      },
      {
        step: 3,
        name: 'Final Sized Orders',
        count: 3,
        subtitle: 'Stage-3 LLM Capital Allocation',
        criteria: 'Volatility Parity position sizing, 1.5 ATR stop loss, faithfulness >= 90%',
        droppedCount: 16,
        sampleDropped: [
          { symbol: 'IRCTC', reason: 'Volatility parity allocated 0% due to volatility spike' },
        ],
      },
    ],
  },
  lynch: {
    personaName: 'Peter Lynch (GARP & Growth)',
    stages: [
      {
        step: 0,
        name: 'Universe Ingestion',
        count: 500,
        subtitle: 'NSE Nifty 500 constituents',
        criteria: '4-period quarterly statements & fundamentals ingested',
        droppedCount: 0,
        sampleDropped: [],
      },
      {
        step: 1,
        name: 'Liquidity Filter',
        count: 348,
        subtitle: 'Stage-1 Quality & Turnover',
        criteria: 'Market cap > ₹1,000 Cr AND 30-day turnover >= ₹5 Cr',
        droppedCount: 152,
        sampleDropped: [{ symbol: 'GTLINFRA', reason: 'Penny illiquidity' }],
      },
      {
        step: 2,
        name: 'GARP Hurdles',
        count: 14,
        subtitle: 'Stage-2 Valuation & Quality',
        criteria: 'PEG <= 1.0 AND ROCE >= 15% AND CFO/PAT >= 0.80',
        droppedCount: 334,
        sampleDropped: [
          { symbol: 'INFY', reason: 'PEG ratio 2.1 exceeds 1.0 hurdle' },
          { symbol: 'PAYTM', reason: 'CFO/PAT negative; zero cash conversion' },
        ],
      },
      {
        step: 3,
        name: 'Final Sized Orders',
        count: 2,
        subtitle: 'Stage-3 Conviction Portfolio',
        criteria: 'Earnings consistency audit and cash flow durability sizing',
        droppedCount: 12,
        sampleDropped: [
          { symbol: 'BRITANNIA', reason: 'Order rejected by broker cash buffer limit' },
        ],
      },
    ],
  },
  marks: {
    personaName: 'Howard Marks (Contrarian Value)',
    stages: [
      {
        step: 0,
        name: 'Universe Ingestion',
        count: 500,
        subtitle: 'NSE Nifty 500 constituents',
        criteria: 'Valuation deciles and cyclical indicators synced',
        droppedCount: 0,
        sampleDropped: [],
      },
      {
        step: 1,
        name: 'Liquidity Filter',
        count: 348,
        subtitle: 'Stage-1 Liquidity check',
        criteria: 'Turnover >= ₹5 Cr AND solvency check',
        droppedCount: 152,
        sampleDropped: [],
      },
      {
        step: 2,
        name: 'Contrarian Distress',
        count: 12,
        subtitle: 'Stage-2 Decile & Solvency',
        criteria: 'P/E in lowest 30% of 5y range AND Debt/Equity <= 0.50',
        droppedCount: 336,
        sampleDropped: [
          { symbol: 'ADANIENT', reason: 'Debt-to-equity 1.45 exceeds 0.50 threshold' },
          { symbol: 'TITAN', reason: 'P/E in 82nd percentile (overpriced momentum)' },
        ],
      },
      {
        step: 3,
        name: 'Final Sized Orders',
        count: 3,
        subtitle: 'Stage-3 Margin of Safety',
        criteria: 'Second-level thinking verification distinguishing panic from fatal flaws',
        droppedCount: 9,
        sampleDropped: [],
      },
    ],
  },
};

export default function WatchlistFunnel() {
  const [selectedPersona, setSelectedPersona] = useState('simons');
  const [activeStep, setActiveStep] = useState<number | null>(null);

  const current = FUNNEL_DATA_BY_PERSONA[selectedPersona] || FUNNEL_DATA_BY_PERSONA.simons;

  return (
    <div className="porcelain-card p-6 space-y-6">
      {/* Header & Persona Selector */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 border-b border-[#E5E2D9] pb-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-mono text-[#D97706] uppercase tracking-wider mb-0.5">
            <Filter className="w-3.5 h-3.5" />
            <span>Multi-Stage Quantitative Filter</span>
          </div>
          <h3 className="text-xl font-serif font-bold text-[#111827]">
            Watchlist Screening Funnel
          </h3>
          <p className="text-xs text-[#4B5563] mt-0.5">
            How 500 Nifty constituents are systematically eliminated by hard quantitative hurdles down to ~3 final orders nightly.
          </p>
        </div>

        {/* Persona Select Chips */}
        <div className="flex items-center gap-1.5 p-1 rounded-lg bg-[#F4F2EC] border border-[#E5E2D9] text-xs font-mono">
          {[
            { id: 'simons', label: 'Simons' },
            { id: 'lynch', label: 'Lynch' },
            { id: 'marks', label: 'Marks' },
          ].map((p) => (
            <button
              key={p.id}
              onClick={() => {
                setSelectedPersona(p.id);
                setActiveStep(null);
              }}
              className={`px-3 py-1 rounded-md transition-all cursor-pointer ${
                selectedPersona === p.id
                  ? 'bg-white font-semibold text-[#111827] shadow-xs'
                  : 'text-[#4B5563] hover:text-[#111827]'
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* Stepped Funnel Horizontal Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3 relative">
        {current.stages.map((st, idx) => {
          const isSelected = activeStep === st.step;
          return (
            <div
              key={st.step}
              onClick={() => setActiveStep(isSelected ? null : st.step)}
              className={`p-4 rounded-xl border transition-all cursor-pointer relative ${
                isSelected
                  ? 'border-[#D97706] bg-amber-50/30 shadow-xs'
                  : 'border-[#E5E2D9] bg-white hover:border-[#D5D0C3]'
              }`}
            >
              <div className="flex justify-between items-center text-[10px] font-mono text-[#9CA3AF] mb-1">
                <span>STAGE {st.step}</span>
                {st.droppedCount > 0 && (
                  <span className="text-rose-600 font-semibold">-{st.droppedCount} dropped</span>
                )}
              </div>

              <div className="text-2xl font-bold font-mono text-[#111827]">
                {st.count} <span className="text-xs font-normal text-[#9CA3AF]">stocks</span>
              </div>

              <div className="text-xs font-semibold text-[#111827] mt-1">{st.name}</div>
              <div className="text-[11px] text-[#4B5563] mt-0.5 leading-snug">{st.subtitle}</div>

              <div className="mt-3 pt-2 border-t border-[#EDEAE2] text-[10px] font-mono text-[#4B5563]">
                {st.criteria}
              </div>

              {idx < 3 && (
                <div className="hidden md:flex absolute -right-3 top-1/2 -translate-y-1/2 z-10 w-6 h-6 rounded-full bg-white border border-[#E5E2D9] items-center justify-center text-[#9CA3AF] shadow-xs">
                  <ChevronRight className="w-3.5 h-3.5" />
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Interactive Step Detail Drawer */}
      {activeStep !== null && (
        <div className="p-4 rounded-xl border border-amber-200/80 bg-amber-50/40 text-xs animate-fade-in font-mono space-y-2">
          <div className="flex items-center justify-between text-amber-950 font-semibold">
            <span>
              Stage {activeStep}: {current.stages[activeStep].name} Inspection
            </span>
            <span className="text-[11px] text-amber-800">
              {current.stages[activeStep].droppedCount} stocks eliminated at this hurdle
            </span>
          </div>

          <p className="text-[11px] text-[#4B5563] font-sans">
            <strong>Rule Applied:</strong> {current.stages[activeStep].criteria}
          </p>

          {current.stages[activeStep].sampleDropped.length > 0 && (
            <div className="space-y-1 pt-1">
              <span className="text-[10px] uppercase text-[#9CA3AF]">
                Sample Elimination Reasons:
              </span>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {current.stages[activeStep].sampleDropped.map((sd, i) => (
                  <div key={i} className="p-2 rounded bg-white border border-amber-200/60 text-[11px]">
                    <span className="font-bold text-[#111827] mr-1.5">{sd.symbol}:</span>
                    <span className="text-[#4B5563]">{sd.reason}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
