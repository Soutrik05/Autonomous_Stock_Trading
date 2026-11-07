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
        subtitle: 'Stage-1 Volume & price bounds',
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
        subtitle: 'Stage-2 Quantitative signal',
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
        subtitle: 'Stage-3 LLM capital allocation',
        criteria: 'Volatility parity position sizing, 1.5 ATR stop loss, faithfulness >= 90%',
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
        subtitle: 'Stage-1 Quality & turnover',
        criteria: 'Market cap > ₹1,000 Cr AND 30-day turnover >= ₹5 Cr',
        droppedCount: 152,
        sampleDropped: [{ symbol: 'GTLINFRA', reason: 'Penny illiquidity' }],
      },
      {
        step: 2,
        name: 'GARP Hurdles',
        count: 14,
        subtitle: 'Stage-2 Valuation & quality',
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
        subtitle: 'Stage-3 Conviction portfolio',
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
        subtitle: 'Stage-2 Decile & solvency',
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
        subtitle: 'Stage-3 Margin of safety',
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
    <div className="arena-glass p-6 sm:p-8 space-y-6">
      {/* Header & Persona Selector */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 border-b border-white/10 pb-5">
        <div>
          <div className="flex items-center gap-1.5 text-xs font-mono text-cyan-400 mb-1">
            <Filter className="w-3.5 h-3.5" />
            <span>Multi-Stage Quantitative Filter</span>
          </div>
          <h3 className="text-xl sm:text-2xl font-bold tracking-tight text-white">
            Watchlist Screening Funnel
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            How 500 Nifty constituents are systematically eliminated by hard quantitative hurdles down to ~3 final orders nightly.
          </p>
        </div>

        {/* Persona Select Chips */}
        <div className="flex items-center gap-1 p-1 rounded-xl bg-white/[0.04] border border-white/10 text-xs font-mono backdrop-blur-md">
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
              className={`px-3.5 py-1.5 rounded-lg transition-all cursor-pointer ${
                selectedPersona === p.id
                  ? 'bg-cyan-500/20 text-cyan-300 font-semibold border border-cyan-500/30 shadow-[0_0_12px_rgba(6,182,212,0.2)]'
                  : 'text-slate-400 hover:text-white'
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
              className={`p-5 rounded-xl border transition-all cursor-pointer relative ${
                isSelected
                  ? 'border-cyan-500/50 bg-cyan-500/10 shadow-[0_0_20px_rgba(6,182,212,0.15)]'
                  : 'border-white/10 bg-white/[0.02] hover:bg-white/[0.05] hover:border-white/20'
              }`}
            >
              <div className="flex justify-between items-center text-[10px] font-mono text-slate-500 mb-1.5">
                <span>STAGE {st.step}</span>
                {st.droppedCount > 0 && (
                  <span className="text-rose-400 font-semibold">-{st.droppedCount} eliminated</span>
                )}
              </div>

              <div className="text-2xl font-bold font-mono text-white">
                {st.count} <span className="text-xs font-normal text-slate-400">stocks</span>
              </div>

              <div className="text-sm font-semibold text-white mt-1">{st.name}</div>
              <div className="text-xs text-slate-400 mt-0.5 leading-snug">{st.subtitle}</div>

              <div className="mt-3.5 pt-2.5 border-t border-white/10 text-[11px] font-mono text-slate-400">
                {st.criteria}
              </div>

              {idx < 3 && (
                <div className="hidden md:flex absolute -right-3 top-1/2 -translate-y-1/2 z-10 w-6 h-6 rounded-full bg-[#0B0F17] border border-white/20 items-center justify-center text-slate-400 shadow-md">
                  <ChevronRight className="w-3.5 h-3.5" />
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Interactive Step Detail Drawer */}
      {activeStep !== null && (
        <div className="arena-glass-subdued p-5 rounded-xl border border-cyan-500/30 text-xs font-mono space-y-2.5">
          <div className="flex items-center justify-between text-white font-semibold">
            <span>
              Stage {activeStep}: {current.stages[activeStep].name} Inspection
            </span>
            <span className="text-xs text-cyan-400">
              {current.stages[activeStep].droppedCount} stocks eliminated at this hurdle
            </span>
          </div>

          <p className="text-xs text-slate-300 font-sans">
            <strong>Rule applied:</strong> {current.stages[activeStep].criteria}
          </p>

          {current.stages[activeStep].sampleDropped.length > 0 && (
            <div className="space-y-2 pt-1.5">
              <span className="text-[10px] uppercase text-slate-500 font-mono tracking-wider">
                Sample elimination reasons:
              </span>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                {current.stages[activeStep].sampleDropped.map((sd, i) => (
                  <div key={i} className="p-3 rounded-lg bg-black/40 border border-white/10 text-xs">
                    <span className="font-bold text-white mr-2">{sd.symbol}:</span>
                    <span className="text-slate-400">{sd.reason}</span>
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
