import { useState, useEffect } from 'react';
import { ChevronRight, CheckCircle2 } from 'lucide-react';
import { apiService } from '../services/api';
import type { FunnelEntry } from '../types';
import { cn } from '../utils/cn';

interface FunnelStage {
  step: number;
  name: string;
  count: number;
  subtitle: string;
  criteria: string;
  droppedCount: number;
  sampleDropped: { symbol: string; reason: string }[];
}

interface PersonaFunnelDef {
  personaName: string;
  stages: FunnelStage[];
}

const DEFAULT_FUNNEL_DATA: Record<string, PersonaFunnelDef> = {
  simons: {
    personaName: 'Jim Simons (Quant Momentum)',
    stages: [
      {
        step: 0,
        name: 'Universe Ingestion',
        count: 221,
        subtitle: 'NSE Universe & Features',
        criteria: 'Daily EOD OHLCV + technical indicators computed point-in-time',
        droppedCount: 0,
        sampleDropped: [],
      },
      {
        step: 1,
        name: 'Liquidity & Volatility',
        count: 9,
        subtitle: 'Volume & Kaufman Bounds',
        criteria: 'Turnover >= ₹5 Cr AND close >= ₹20 AND Kaufman ER > 0.40',
        droppedCount: 212,
        sampleDropped: [
          { symbol: 'RELIANCE', reason: 'Kaufman ER is 0.38 (below 0.40 hurdle)' },
          { symbol: 'TCS', reason: 'ADX is 18.2 (insufficient trend strength)' },
        ],
      },
      {
        step: 2,
        name: 'Momentum Ranking',
        count: 12,
        subtitle: 'Watchlist Candidates',
        criteria: 'Kaufman ER, ADX 14 >= 25, positive skew_60, sector cap',
        droppedCount: 0,
        sampleDropped: [
          { symbol: 'SUZLON', reason: 'Turnover volatility spike exceeded risk budget' },
        ],
      },
      {
        step: 3,
        name: 'Sized Orders',
        count: 2,
        subtitle: 'Portfolio Allocations',
        criteria: 'Volatility parity sizing, ATR trailing stop, LLM fidelity',
        droppedCount: 10,
        sampleDropped: [
          { symbol: 'HINDPETRO', reason: 'Queued for market open at 09:15 IST' },
        ],
      },
    ],
  },
  varsity: {
    personaName: 'StockMinds Core (Zerodha Varsity Confluence)',
    stages: [
      {
        step: 0,
        name: 'Universe Ingestion',
        count: 499,
        subtitle: 'NSE Nifty 500 Constituents',
        criteria: 'Daily technicals + balance-sheet solvency ratios point-in-time',
        droppedCount: 0,
        sampleDropped: [],
      },
      {
        step: 1,
        name: 'Dual Confluence Screen',
        count: 40,
        subtitle: 'Solvency DCF + Trend',
        criteria: 'Debt/Equity <= 1.5 AND ROCE >= 12% AND Close > 200 EMA AND RSI 45–68',
        droppedCount: 459,
        sampleDropped: [
          { symbol: 'TATACHEM', reason: 'Debt/Equity 1.8x exceeds 1.5 hurdle' },
          { symbol: 'WIPRO', reason: 'Trading below 200 EMA in primary downtrend' },
        ],
      },
      {
        step: 2,
        name: 'Quality & Valuation',
        count: 10,
        subtitle: 'Watchlist Candidates',
        criteria: 'Strict 1:1.5 Risk-Reward minimum, volume surge >= 1.0x',
        droppedCount: 30,
        sampleDropped: [
          { symbol: 'INFY', reason: 'Risk/Reward ratio 1:1.1 is below 1:1.5 threshold' },
        ],
      },
      {
        step: 3,
        name: 'Sized Orders',
        count: 4,
        subtitle: 'Target Buys Sized',
        criteria: 'Max 10% risk per position, sector exposure <= 25%',
        droppedCount: 6,
        sampleDropped: [
          { symbol: 'COALINDIA', reason: 'Sector exposure cap (25% Energy) reached' },
        ],
      },
    ],
  },
  lynch: {
    personaName: 'Peter Lynch (GARP)',
    stages: [
      {
        step: 0,
        name: 'Universe Ingestion',
        count: 499,
        subtitle: 'NSE Nifty 500 Constituents',
        criteria: 'Financial statements, quarterly earnings, PEG, CFO/PAT ratios',
        droppedCount: 0,
        sampleDropped: [],
      },
      {
        step: 1,
        name: 'GARP Fundamentals',
        count: 28,
        subtitle: 'P/E to Growth Screen',
        criteria: 'PEG <= 1.2 AND CFO/PAT >= 0.8 AND Debt/Equity <= 1.0 AND ROCE >= 15%',
        droppedCount: 471,
        sampleDropped: [
          { symbol: 'ADANIENT', reason: 'PEG 2.8x exceeds 1.2 hurdle' },
          { symbol: 'VEDL', reason: 'Debt/Equity 1.9x exceeds 1.0 threshold' },
        ],
      },
      {
        step: 2,
        name: 'Cash Conversion Rank',
        count: 8,
        subtitle: 'Watchlist Candidates',
        criteria: 'Free cash flow margin, inventory turnover trend, insider ownership',
        droppedCount: 20,
        sampleDropped: [
          { symbol: 'HCLTECH', reason: 'Stagnant operating cash flow margin' },
        ],
      },
      {
        step: 3,
        name: 'Sized Orders',
        count: 3,
        subtitle: 'Conviction Positions',
        criteria: 'Equal-weight compounding allocation, maximum 8 holdings',
        droppedCount: 5,
        sampleDropped: [
          { symbol: 'LICI', reason: 'Position deferred due to margin pressure' },
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
        count: 499,
        subtitle: 'NSE Nifty 500 Constituents',
        criteria: 'Price-to-Book, historical drawdown, interest coverage, solvency',
        droppedCount: 0,
        sampleDropped: [],
      },
      {
        step: 1,
        name: 'Distress & Solvency',
        count: 18,
        subtitle: 'Cyclical Despair Screen',
        criteria: 'Close within 20% of 52-week low AND Interest Coverage >= 3.0x',
        droppedCount: 481,
        sampleDropped: [
          { symbol: 'ZEEL', reason: 'Interest coverage 1.4x indicates solvency risk' },
        ],
      },
      {
        step: 2,
        name: 'Second-Level Margin',
        count: 6,
        subtitle: 'Watchlist Candidates',
        criteria: 'Tangible book value discount, depressed cyclical margins',
        droppedCount: 12,
        sampleDropped: [
          { symbol: 'BHEL', reason: 'Working capital cycle extended beyond limit' },
        ],
      },
      {
        step: 3,
        name: 'Sized Orders',
        count: 2,
        subtitle: 'Deep Value Entries',
        criteria: 'Wide sizing buffers, no mechanical stops, patience horizon',
        droppedCount: 4,
        sampleDropped: [
          { symbol: 'SAIL', reason: 'Waiting for margin stabilization confirmation' },
        ],
      },
    ],
  },
  jhunjhunwala: {
    personaName: 'Rakesh Jhunjhunwala (Structural Growth)',
    stages: [
      {
        step: 0,
        name: 'Universe Ingestion',
        count: 499,
        subtitle: 'NSE Nifty 500 Constituents',
        criteria: 'Capex intensity, promoter holding, revenue growth, sectoral TAM',
        droppedCount: 0,
        sampleDropped: [],
      },
      {
        step: 1,
        name: 'High-Growth Promoters',
        count: 32,
        subtitle: 'Capex & Moat Screen',
        criteria: 'Promoter pledge = 0% AND Promoter Holding >= 50% AND 3Y Sales CAGR >= 15%',
        droppedCount: 467,
        sampleDropped: [
          { symbol: 'GMRINFRA', reason: 'Promoter pledge 14.5% breaches zero-pledge rule' },
        ],
      },
      {
        step: 2,
        name: 'Conviction Ranking',
        count: 9,
        subtitle: 'Watchlist Candidates',
        criteria: 'Return on invested capital, operating leverage, capex cycle phase',
        droppedCount: 23,
        sampleDropped: [
          { symbol: 'POLYCAB', reason: 'Valuation multiples exceed ceiling' },
        ],
      },
      {
        step: 3,
        name: 'Sized Orders',
        count: 4,
        subtitle: 'Pyramided Holdings',
        criteria: 'High-conviction sizing, 15-20% portfolio weight per position',
        droppedCount: 5,
        sampleDropped: [
          { symbol: 'TATACOMM', reason: 'Awaiting pullback to pyramiding support' },
        ],
      },
    ],
  },
};

interface WatchlistFunnelProps {
  initialAgentId?: string;
}

export default function WatchlistFunnel({ initialAgentId }: WatchlistFunnelProps) {
  const normalizeKey = (id: string | undefined): string => {
    if (!id) return 'simons';
    const clean = id.toLowerCase().replace('baseline-', '').replace('-rules', '');
    if (clean.includes('simons')) return 'simons';
    if (clean.includes('lynch')) return 'lynch';
    if (clean.includes('marks')) return 'marks';
    if (clean.includes('jhunjhunwala') || clean.includes('rj')) return 'jhunjhunwala';
    if (clean.includes('varsity') || clean.includes('core')) return 'varsity';
    return 'simons';
  };

  const [selectedPersona, setSelectedPersona] = useState<string>(() => normalizeKey(initialAgentId));
  const [activeStep, setActiveStep] = useState<number>(1);
  const [liveFunnels, setLiveFunnels] = useState<Record<string, FunnelEntry>>({});
  const [isLiveLoaded, setIsLiveLoaded] = useState<boolean>(false);

  useEffect(() => {
    if (initialAgentId) {
      setSelectedPersona(normalizeKey(initialAgentId));
    }
  }, [initialAgentId]);

  useEffect(() => {
    async function fetchFunnelData() {
      try {
        const funnels = await apiService.getFunnel();
        if (Array.isArray(funnels) && funnels.length > 0) {
          const map: Record<string, FunnelEntry> = {};
          funnels.forEach((f) => {
            const key = normalizeKey(f.agentId);
            map[key] = f;
          });
          setLiveFunnels(map);
          setIsLiveLoaded(true);
        }
      } catch {
        // Fallback gracefully
      }
    }
    fetchFunnelData();
  }, []);

  const defaultData = DEFAULT_FUNNEL_DATA[selectedPersona] || DEFAULT_FUNNEL_DATA.simons;
  const liveEntry = liveFunnels[selectedPersona];

  // Synthesize live stage counts
  const effectiveStages = defaultData.stages.map((st, idx) => {
    if (!liveEntry || !liveEntry.stages) return st;

    let liveCount = st.count;
    if (idx === 0) {
      const s0 = liveEntry.stages.find((s) => s.key === 'stage0');
      if (s0) liveCount = s0.count;
    } else if (idx === 1) {
      const s1 = liveEntry.stages.find((s) => s.key === 'stage1');
      if (s1) liveCount = s1.count;
    } else if (idx === 2) {
      const fin = liveEntry.stages.find((s) => s.key === 'final');
      if (fin) liveCount = fin.count;
    }

    return {
      ...st,
      count: liveCount,
    };
  });

  for (let i = 1; i < effectiveStages.length; i++) {
    const prev = effectiveStages[i - 1].count;
    const curr = effectiveStages[i].count;
    effectiveStages[i].droppedCount = Math.max(0, prev - curr);
  }

  const selectedStage = effectiveStages[activeStep] || effectiveStages[1];

  return (
    <div className="bg-[#161616] border border-border-hairline rounded-lg font-sans overflow-hidden">
      {/* 1. Header with Persona Switcher */}
      <div className="p-4 sm:p-5 border-b border-border-hairline flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 font-mono text-xs">
        <div className="flex items-center gap-2">
          <h3 className="font-serif text-lg font-medium text-white tracking-tight">
            Screening Pipeline
          </h3>
          {isLiveLoaded && liveEntry && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono bg-emerald-500/10 text-positive border border-emerald-500/20">
              <CheckCircle2 className="w-3 h-3" />
              <span>{liveEntry.runDate || 'Live'}</span>
            </span>
          )}
        </div>

        {/* Persona Tabs */}
        <div className="flex items-center p-0.5 rounded bg-[#121212] border border-border-hairline text-xs font-mono overflow-x-auto max-w-full">
          {[
            { id: 'simons', label: 'Simons' },
            { id: 'varsity', label: 'Varsity' },
            { id: 'lynch', label: 'Lynch' },
            { id: 'marks', label: 'Marks' },
            { id: 'jhunjhunwala', label: 'RJ' },
          ].map((p) => (
            <button
              key={p.id}
              onClick={() => setSelectedPersona(p.id)}
              className={cn(
                "px-2.5 py-1 rounded transition-colors cursor-pointer whitespace-nowrap",
                selectedPersona === p.id
                  ? "bg-white/10 text-white font-medium"
                  : "text-zinc-400 hover:text-white"
              )}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* 2. Horizontal Pipeline Stepper (Option A) */}
      <div className="p-4 sm:p-5 border-b border-border-hairline bg-white/[0.01]">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {effectiveStages.map((st, idx) => {
            const isSelected = activeStep === st.step;

            return (
              <button
                key={st.step}
                onClick={() => setActiveStep(st.step)}
                className={cn(
                  "p-3.5 rounded-lg border text-left font-mono transition-all cursor-pointer relative",
                  isSelected
                    ? "bg-white/[0.06] border-white/30 ring-1 ring-white/20"
                    : "bg-[#141414] border-border-hairline hover:border-white/15 hover:bg-white/[0.02]"
                )}
              >
                <div className="flex items-center justify-between text-[10px] text-zinc-500">
                  <span className="font-semibold uppercase tracking-wider">
                    Stage {st.step}
                  </span>
                  {idx > 0 && st.droppedCount > 0 && (
                    <span className="text-negative font-medium">
                      -{st.droppedCount}
                    </span>
                  )}
                </div>

                <div className="text-xl sm:text-2xl font-bold text-white mt-1 tabular-nums">
                  {st.count}
                </div>

                <div className="text-xs text-zinc-300 font-sans mt-0.5 font-medium truncate">
                  {st.name}
                </div>

                {/* Step Connector Arrow Indicator */}
                {idx < effectiveStages.length - 1 && (
                  <div className="hidden lg:block absolute -right-2 top-1/2 -translate-y-1/2 z-10 text-zinc-600 pointer-events-none">
                    <ChevronRight className="w-3.5 h-3.5" />
                  </div>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* 3. Stage Inspection Details (Flat, Zero Inner Cards) */}
      <div className="p-4 sm:p-5 space-y-3 font-mono text-xs">
        {/* Stage Hurdle Summary Bar */}
        <div className="flex flex-col sm:flex-row sm:items-baseline justify-between gap-2 pb-2.5 border-b border-border-hairline">
          <div className="space-y-0.5">
            <span className="text-[10px] uppercase text-zinc-500 font-sans tracking-wider block">
              Stage {selectedStage.step} Hurdle · {selectedStage.name}
            </span>
            <code className="text-xs text-zinc-200 font-mono">
              {selectedStage.criteria}
            </code>
          </div>

          {selectedStage.droppedCount > 0 && (
            <span className="text-negative text-xs font-semibold tabular-nums whitespace-nowrap">
              -{selectedStage.droppedCount} eliminated
            </span>
          )}
        </div>

        {/* Flat Eliminated Candidates List (Hairline Separated, No Boxed Cards) */}
        {selectedStage.sampleDropped.length > 0 && (
          <div className="space-y-1.5 pt-1">
            <span className="text-[10px] uppercase text-zinc-500 block font-sans tracking-wider">
              Sample Elimination Telemetry
            </span>
            <div className="divide-y divide-border-hairline border-t border-b border-border-hairline">
              {selectedStage.sampleDropped.map((sd, i) => (
                <div key={i} className="py-2 flex items-baseline justify-between gap-4 font-mono text-xs">
                  <span className="font-bold text-white flex-shrink-0">
                    {sd.symbol}
                  </span>
                  <span className="text-zinc-400 font-sans text-xs text-right">
                    {sd.reason}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
