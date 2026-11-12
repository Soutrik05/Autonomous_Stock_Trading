import { useState, useEffect } from 'react';
import { Filter, CheckCircle2 } from 'lucide-react';
import { apiService } from '../services/api';
import type { FunnelEntry } from '../types';

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
        subtitle: 'NSE Universe & Technical Features',
        criteria: 'Daily EOD OHLCV + technical indicators computed point-in-time',
        droppedCount: 0,
        sampleDropped: [],
      },
      {
        step: 1,
        name: 'Liquidity & Volatility Filter',
        count: 9,
        subtitle: 'Volume Bounds & Kaufman Efficiency',
        criteria: '20-day median turnover >= ₹5 Cr AND close >= ₹20 AND Kaufman ER > 0.40',
        droppedCount: 212,
        sampleDropped: [
          { symbol: 'RELIANCE', reason: 'Kaufman ER is 0.38 (below 0.40 hurdle - choppy regime)' },
          { symbol: 'TCS', reason: 'ADX is 18.2 (insufficient directional trend strength)' },
        ],
      },
      {
        step: 2,
        name: 'Directional Momentum Ranking',
        count: 12,
        subtitle: 'Watchlist Candidates (TTL Locked)',
        criteria: 'Kaufman ER, ADX 14 >= 25, positive skew_60, and sector-capped allocation',
        droppedCount: 0,
        sampleDropped: [
          { symbol: 'SUZLON', reason: 'Turnover volatility spike exceeded risk budget' },
        ],
      },
      {
        step: 3,
        name: 'Autonomous Sized Orders',
        count: 2,
        subtitle: 'Active Portfolio Allocations',
        criteria: 'Volatility parity sizing, ATR trailing stop, and LLM sizing fidelity check',
        droppedCount: 10,
        sampleDropped: [
          { symbol: 'HINDPETRO', reason: 'Order queued for market execution at 09:15 IST' },
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
        criteria: 'Daily technicals + balance-sheet solvency ratios ingested point-in-time',
        droppedCount: 0,
        sampleDropped: [],
      },
      {
        step: 1,
        name: 'Dual Confluence Screen',
        count: 40,
        subtitle: 'Solvency DCF + Trend Alignment',
        criteria: 'Debt/Equity <= 1.5 AND ROCE >= 12% AND Close > 200 EMA AND RSI 45–68',
        droppedCount: 459,
        sampleDropped: [
          { symbol: 'TATACHEM', reason: 'Debt/Equity 1.8x exceeds 1.5 balance-sheet hurdle' },
          { symbol: 'WIPRO', reason: 'Trading below 200 EMA (The Mothership) in primary downtrend' },
        ],
      },
      {
        step: 2,
        name: 'Relative Valuation & Quality Rank',
        count: 10,
        subtitle: 'Watchlist Candidates (TTL Locked)',
        criteria: 'Strict 1:1.5 Risk-Reward minimum, volume surge >= 1.0x, sector diversification',
        droppedCount: 30,
        sampleDropped: [
          { symbol: 'BHARTIARTL', reason: 'Risk-to-reward ratio 1.2 falls below 1.5 hurdle' },
        ],
      },
      {
        step: 3,
        name: 'Autonomous Sized Orders',
        count: 1,
        subtitle: 'High-Confluence Swings',
        criteria: 'Disciplined swing trade sizing with ATR trailing stop and patience protocol',
        droppedCount: 9,
        sampleDropped: [
          { symbol: 'INFY', reason: 'Setup intact; held in reserve awaiting pullback to support' },
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
        count: 499,
        subtitle: 'NSE Nifty 500 Constituents',
        criteria: 'Quarterly fundamentals, operating cash flows, and PEG matrices ingested',
        droppedCount: 0,
        sampleDropped: [],
      },
      {
        step: 1,
        name: 'GARP Valuation & Quality Filter',
        count: 26,
        subtitle: 'PEG Bounds & Capital Productivity',
        criteria: 'PEG <= 1.0 AND ROCE >= 15% AND CFO/PAT >= 0.80 AND Market Cap > ₹1,000 Cr',
        droppedCount: 473,
        sampleDropped: [
          { symbol: 'INFY', reason: 'PEG ratio 2.1 exceeds 1.0 hurdle' },
          { symbol: 'PAYTM', reason: 'CFO/PAT negative; zero operating cash flow conversion' },
        ],
      },
      {
        step: 2,
        name: 'Earnings Quality & Sector Diversification',
        count: 10,
        subtitle: 'Watchlist Candidates (TTL Locked)',
        criteria: 'Multi-quarter earnings compounding, balance-sheet safety, and sector capping',
        droppedCount: 16,
        sampleDropped: [
          { symbol: 'HCLTECH', reason: 'Sub-hurdle free cash flow yield vs peers' },
        ],
      },
      {
        step: 3,
        name: 'Autonomous Sized Orders',
        count: 2,
        subtitle: 'High-Conviction Compounders',
        criteria: 'Equal-weight risk budget with operational margin check and multi-month horizon',
        droppedCount: 8,
        sampleDropped: [
          { symbol: 'PAGEIND', reason: 'Valuation near upper quartile boundary; awaiting entry pullback' },
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
        criteria: 'Cyclical indicators, balance sheets, and 52-week drawdown scans',
        droppedCount: 0,
        sampleDropped: [],
      },
      {
        step: 1,
        name: 'Solvency & Asymmetric Safety Screen',
        count: 9,
        subtitle: 'Solvency Buffer & Debt Coverage',
        criteria: 'Net debt/EBITDA < 3.0x AND interest coverage >= 2.5x AND deep cyclical value',
        droppedCount: 490,
        sampleDropped: [
          { symbol: 'VEDL', reason: 'Debt/EBITDA 3.8x exceeds solvency boundary' },
          { symbol: 'TITAN', reason: 'Trading at 92nd percentile valuation; zero safety margin' },
        ],
      },
      {
        step: 2,
        name: 'Margin of Safety Ranking',
        count: 11,
        subtitle: 'Watchlist Candidates (TTL Locked)',
        criteria: 'Price within 15% of 52-week low or bottom decile P/E with unencumbered assets',
        droppedCount: 0,
        sampleDropped: [
          { symbol: 'ZEEL', reason: 'Governance risk flagged in secondary qualitative audit' },
        ],
      },
      {
        step: 3,
        name: 'Autonomous Sized Orders',
        count: 2,
        subtitle: 'Second-Level Asymmetric Allocations',
        criteria: 'Contrarian allocation with thesis autopsy and multi-quarter holding patience',
        droppedCount: 9,
        sampleDropped: [
          { symbol: 'IOC', reason: 'Awaiting cyclical bottom confirmation before allocation' },
        ],
      },
    ],
  },
  jhunjhunwala: {
    personaName: 'Rakesh Jhunjhunwala (Domestic Capex & Compounding)',
    stages: [
      {
        step: 0,
        name: 'Universe Ingestion',
        count: 221,
        subtitle: 'NSE Universe & Corporate Fundamentals',
        criteria: 'Promoter holdings, capex cycles, and multi-year ROCE statements ingested',
        droppedCount: 0,
        sampleDropped: [],
      },
      {
        step: 1,
        name: 'Structural Compounding Filter',
        count: 3,
        subtitle: 'Promoter Quality & Operating Leverage',
        criteria: 'Promoter holding >= 50% AND ROCE >= 18% AND Sector Capex Tailwinds',
        droppedCount: 218,
        sampleDropped: [
          { symbol: 'YESBANK', reason: 'Promoter skin-in-the-game boundary violated' },
          { symbol: 'SAIL', reason: 'Cyclical commoditization without structural pricing moat' },
        ],
      },
      {
        step: 2,
        name: 'High-Conviction Compounders',
        count: 4,
        subtitle: 'Watchlist Candidates (TTL Locked)',
        criteria: 'Structural compounding narrative, sector leadership, and long-term moat',
        droppedCount: 0,
        sampleDropped: [
          { symbol: 'DLF', reason: 'Sub-hurdle balance sheet leverage vs peers' },
        ],
      },
      {
        step: 3,
        name: 'Autonomous Sized Orders',
        count: 2,
        subtitle: 'Secular Growth Positions',
        criteria: 'Pyramiding into high-conviction winners with multi-quarter patience protocol',
        droppedCount: 2,
        sampleDropped: [
          { symbol: 'TATAMOTORS', reason: 'Held in core portfolio; no incremental tranche required' },
        ],
      },
    ],
  },
};

const WIDTH_CLASSES = [
  'w-full max-w-2xl',
  'w-full max-w-xl',
  'w-full max-w-md',
  'w-full max-w-xs',
];

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
  const [activeStep, setActiveStep] = useState<number | null>(null);
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
        // Fallback gracefully to default configurations
      }
    }
    fetchFunnelData();
  }, []);

  const defaultData = DEFAULT_FUNNEL_DATA[selectedPersona] || DEFAULT_FUNNEL_DATA.simons;
  const liveEntry = liveFunnels[selectedPersona];

  // Synthesize live API stage counts with qualitative stage definitions
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

  // Recompute drop counts dynamically
  for (let i = 1; i < effectiveStages.length; i++) {
    const prev = effectiveStages[i - 1].count;
    const curr = effectiveStages[i].count;
    effectiveStages[i].droppedCount = Math.max(0, prev - curr);
  }

  return (
    <div className="bg-[#161616] border border-border-hairline p-5 sm:p-6 rounded-lg space-y-6 font-sans">
      {/* Header & Persona Selector */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 border-b border-border-hairline pb-4">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="font-serif text-lg sm:text-xl font-medium tracking-tight text-white flex items-center gap-2">
              <Filter className="w-4 h-4 text-accent" />
              <span>Active Watchlist Candidate Elimination Funnel</span>
            </h3>
            {isLiveLoaded && liveEntry && (
              <span className="hidden sm:inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono bg-emerald-500/10 text-positive border border-emerald-500/20">
                <CheckCircle2 className="w-3 h-3" />
                <span>Live Pipeline {liveEntry.runDate || new Date().toISOString().split('T')[0]}</span>
              </span>
            )}
          </div>
          <p className="text-xs text-zinc-400 font-mono mt-0.5">
            Stage-by-stage quantitative attrition from broad universe to final sized orders
          </p>
        </div>

        {/* Persona Selector Tabs for all 5 strategies */}
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
              onClick={() => {
                setSelectedPersona(p.id);
                setActiveStep(null);
              }}
              className={`px-3 py-1 rounded transition-colors cursor-pointer whitespace-nowrap ${
                selectedPersona === p.id
                  ? 'bg-white/[0.12] text-accent font-semibold border border-accent/30'
                  : 'text-zinc-400 hover:text-white'
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* True Visually Tapered Funnel Geometry */}
      <div className="flex flex-col items-center space-y-3 py-2">
        {effectiveStages.map((st, idx) => {
          const isSelected = activeStep === st.step;
          const widthClass = WIDTH_CLASSES[idx] || 'w-full max-w-sm';

          return (
            <div key={st.step} className="w-full flex flex-col items-center">
              {/* Elimination Dropoff Bridge between stages */}
              {idx > 0 && (
                <div className="flex items-center gap-2 text-[10px] font-mono text-zinc-500 py-1">
                  <span>↓</span>
                  <span className="text-negative font-medium">
                    {st.droppedCount} eliminated
                  </span>
                  <span>·</span>
                  <span className="truncate max-w-[260px] text-zinc-500">{st.subtitle}</span>
                </div>
              )}

              {/* Tapered Funnel Block */}
              <div
                onClick={() => setActiveStep(isSelected ? null : st.step)}
                className={`${widthClass} p-3.5 sm:p-4 rounded border transition-all cursor-pointer font-mono text-xs ${
                  isSelected
                    ? 'border-accent bg-accent/10'
                    : 'border-border-hairline bg-[#121212] hover:border-white/20 hover:bg-white/[0.03]'
                }`}
              >
                <div className="flex items-center justify-between text-[11px]">
                  <span className="text-zinc-500 font-semibold">STAGE {st.step}</span>
                  <span className="font-bold text-white text-sm sm:text-base tabular-nums">
                    {st.count} <span className="text-xs font-normal text-zinc-400">stocks</span>
                  </span>
                </div>

                <div className="text-sm font-semibold text-white mt-1 font-sans">{st.name}</div>
                <div className="text-xs text-zinc-400 font-sans mt-0.5">{st.criteria}</div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Interactive Step Detail Drawer */}
      {activeStep !== null && effectiveStages[activeStep] && (
        <div className="p-4 sm:p-5 rounded border border-border-hairline bg-[#121212] text-xs font-mono space-y-3 animate-hero-entrance">
          <div className="flex items-center justify-between text-white font-semibold border-b border-border-hairline pb-2">
            <span>
              Stage {activeStep}: {effectiveStages[activeStep].name} Inspection
            </span>
            <span className="text-xs text-negative font-mono">
              {effectiveStages[activeStep].droppedCount} stocks eliminated at this hurdle
            </span>
          </div>

          <p className="text-xs text-zinc-300 font-sans">
            <strong>Rule applied:</strong> {effectiveStages[activeStep].criteria}
          </p>

          {effectiveStages[activeStep].sampleDropped.length > 0 && (
            <div className="space-y-2 pt-1">
              <span className="text-[10px] uppercase text-zinc-500 font-mono tracking-wider block">
                Sample elimination reasons:
              </span>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                {effectiveStages[activeStep].sampleDropped.map((sd, i) => (
                  <div key={i} className="p-2.5 rounded bg-[#161616] border border-border-hairline text-xs">
                    <span className="font-bold text-white mr-2">{sd.symbol}:</span>
                    <span className="text-zinc-400">{sd.reason}</span>
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
