import { Link } from 'react-router-dom';
import { Target, Scale } from 'lucide-react';
import type { AgentLeaderboardEntry } from '../types';
import { formatPct } from '../utils/formatters';

interface HeadToHeadDuelsTableProps {
  agents: AgentLeaderboardEntry[];
}

interface DuelPairDefinition {
  id: string;
  philosophyName: string;
  methodology: string;
  llmId: string;
  rulesId: string;
  llmModel: string;
  holdingHorizon: string;
  coreHypothesis: string;
  llmDisplayName: string;
  rulesDisplayName: string;
}

const DUEL_PAIRS: DuelPairDefinition[] = [
  {
    id: 'quant-momentum',
    philosophyName: 'Quantitative Momentum',
    methodology: 'Statistical Trend Efficiency · Volatility Parity · Fast Pruning',
    llmId: 'simons',
    rulesId: 'baseline-simons-rules',
    llmModel: 'Gemini 3.1 Flash Lite',
    holdingHorizon: '1–10 Days',
    coreHypothesis: 'Can dynamic reasoning adapt stop distances and momentum exits faster than a static 2.5x ATR trailing stop?',
    llmDisplayName: 'Jim Simons',
    rulesDisplayName: 'Baseline: Jim Simons',
  },
  {
    id: 'dual-confluence',
    philosophyName: 'Dual Confluence Swing',
    methodology: 'Zerodha Varsity Confluence · Fundamental Solvency + EMA Trend',
    llmId: 'varsity',
    rulesId: 'baseline-varsity-rules',
    llmModel: 'Gemini 3.1 Flash Lite',
    holdingHorizon: '5–20 Days',
    coreHypothesis: 'Can contextual synthesis combine balance-sheet conservatism with technical entry timing more cleanly than rigid sequential hurdles?',
    llmDisplayName: 'StockMinds Core',
    rulesDisplayName: 'Baseline: Varsity Core',
  },
  {
    id: 'garp-peg',
    philosophyName: 'GARP Compounding',
    methodology: 'Peter Lynch Framework · PEG Ratio <= 1.0 · Durable ROCE Growth',
    llmId: 'lynch',
    rulesId: 'baseline-lynch-rules',
    llmModel: 'Gemini 3.1 Flash Lite',
    holdingHorizon: '15–60 Days',
    coreHypothesis: 'Can narrative evaluation distinguish genuine multi-quarter operating margin expansion from cyclical value traps?',
    llmDisplayName: 'Peter Lynch',
    rulesDisplayName: 'Baseline: Peter Lynch',
  },
  {
    id: 'contrarian-value',
    philosophyName: 'Contrarian Margin of Safety',
    methodology: 'Howard Marks Second-Level Thinking · Cyclical Distress · Asymmetric Risk',
    llmId: 'marks',
    rulesId: 'baseline-marks-rules',
    llmModel: 'Gemini 3.1 Flash Lite',
    holdingHorizon: '30–90 Days',
    coreHypothesis: 'Can qualitative second-level thinking identify whether a 52-week low represents forced institutional liquidation or terminal solvency impairment?',
    llmDisplayName: 'Howard Marks',
    rulesDisplayName: 'Baseline: Howard Marks',
  },
  {
    id: 'secular-growth',
    philosophyName: 'Secular Domestic Growth',
    methodology: 'Rakesh Jhunjhunwala Thematic Compounding · Promoter Skin · Sector Leaders',
    llmId: 'jhunjhunwala',
    rulesId: 'baseline-rj-rules',
    llmModel: 'Gemini 3.1 Flash Lite',
    holdingHorizon: '90–180 Days',
    coreHypothesis: 'Can thematic conviction comfortably absorb interim drawdown volatility to pyramid into secular India capex winners?',
    llmDisplayName: 'Rakesh Jhunjhunwala',
    rulesDisplayName: 'Baseline: Rakesh Jhunjhunwala',
  },
];

export default function HeadToHeadDuelsTable({ agents }: HeadToHeadDuelsTableProps) {
  // Map agents by id for O(1) lookup
  const agentMap = new Map<string, AgentLeaderboardEntry>();
  agents.forEach((a) => {
    agentMap.set(a.id, a);
    if (a.id === 'varsity') agentMap.set('stockminds-core', a);
    if (a.id === 'stockminds-core') agentMap.set('varsity', a);
    if (a.id === 'baseline-varsity') agentMap.set('baseline-varsity-rules', a);

    const stripped = a.id.replace('baseline-', '').replace('-rules', '');
    if (!agentMap.has(stripped)) {
      agentMap.set(stripped, a);
    }
  });

  // Calculate pairs telemetry
  const duels = DUEL_PAIRS.map((pair) => {
    const llm = agentMap.get(pair.llmId);
    const rules = agentMap.get(pair.rulesId);

    const llmReturn = llm?.returnPct ?? 0;
    const rulesReturn = rules?.returnPct ?? 0;
    const deltaReturn = llmReturn - rulesReturn;

    const llmSharpe = llm?.sharpeRatio ?? 0;
    const rulesSharpe = rules?.sharpeRatio ?? 0;
    const deltaSharpe = llmSharpe - rulesSharpe;

    const isLlmAhead = deltaReturn > 0.05;
    const isRulesAhead = deltaReturn < -0.05;

    return {
      pair,
      llm,
      rules,
      llmReturn,
      rulesReturn,
      deltaReturn,
      deltaSharpe,
      isLlmAhead,
      isRulesAhead,
    };
  });

  const llmLeadingCount = duels.filter((d) => d.isLlmAhead).length;
  const meanEdge =
    duels.length > 0
      ? duels.reduce((acc, d) => acc + d.deltaReturn, 0) / duels.length
      : 0;

  return (
    <div className="space-y-8">
      {/* 1. AGGREGATE BENCHMARK TELEMETRY */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 p-5 sm:p-6 cosmic-card rounded-xl">
        <div>
          <div className="flex items-center gap-1.5 text-xs font-sans uppercase tracking-wider text-zinc-400 font-medium">
            <Scale className="w-3.5 h-3.5 text-zinc-500" />
            <span>Mean Alpha Spread</span>
          </div>
          <div
            className={`text-3xl font-mono font-bold mt-1.5 tabular-nums ${
              meanEdge > 0 ? 'text-emerald-400' : meanEdge < 0 ? 'text-rose-400' : 'text-zinc-200'
            }`}
          >
            {formatPct(meanEdge)}
          </div>
          <span className="text-xs font-sans text-zinc-500 mt-0.5 block">
            Average excess return of LLM vs. matched rules baseline
          </span>
        </div>

        <div>
          <span className="text-xs font-sans uppercase tracking-wider text-zinc-400 font-medium block">
            LLM Outperformance Rate
          </span>
          <div className="text-3xl font-mono font-bold text-white mt-1.5 tabular-nums">
            {llmLeadingCount} <span className="text-lg font-sans text-zinc-500 font-normal">/ {duels.length}</span>
          </div>
          <span className="text-xs font-sans text-zinc-500 mt-0.5 block">
            Active philosophy pairs where LLM leads net return
          </span>
        </div>

        <div>
          <span className="text-xs font-sans uppercase tracking-wider text-zinc-400 font-medium block">
            Benchmark Universe
          </span>
          <div className="text-base font-sans font-semibold mt-2.5 text-zinc-200">
            NSE Nifty 500
          </div>
          <span className="text-xs font-sans text-zinc-500 mt-0.5 block">
            Integer paise cash accounting with statutory fees
          </span>
        </div>

        <div>
          <span className="text-xs font-sans uppercase tracking-wider text-zinc-400 font-medium block">
            Active Heuristic Library
          </span>
          <div className="text-3xl font-mono font-bold text-white mt-1.5 tabular-nums">
            12 Rules
          </div>
          <span className="text-xs font-sans text-zinc-500 mt-0.5 block">
            Active and reinforced learning heuristics
          </span>
        </div>
      </div>

      {/* 2. PHILOSOPHY MATCHUPS */}
      <div className="space-y-4">
        <div className="flex justify-between items-center border-b border-white/[0.08] pb-3">
          <h2 className="font-display text-2xl font-normal tracking-tight text-white">
            Philosophy Matchups
          </h2>
          <span className="text-xs font-mono text-zinc-400 font-medium">
            5 Active Comparisons
          </span>
        </div>

        {/* Quiet shared column reference header across matchups */}
        <div className="hidden sm:grid grid-cols-12 px-5 py-1 text-[10px] font-mono uppercase tracking-widest text-zinc-500">
          <div className="col-span-4">Strategy</div>
          <div className="col-span-2 text-right">Net Return (%)</div>
          <div className="col-span-2 text-right">Δ vs Nifty (%)</div>
          <div className="col-span-1 text-right">Sharpe</div>
          <div className="col-span-1 text-right">Max DD (%)</div>
          <div className="col-span-2 text-right">Win Rate (%)</div>
        </div>

        <div className="space-y-4">
          {duels.map((duel, idx) => {
            const {
              pair,
              llm,
              rules,
              llmReturn,
              rulesReturn,
            } = duel;

            const llmAlpha = llm?.alphaVsBenchmarkPct ?? 0;
            const rulesAlpha = rules?.alphaVsBenchmarkPct ?? 0;

            const llmSharpe = llm?.sharpeRatio ?? 0;
            const rulesSharpe = rules?.sharpeRatio ?? 0;

            const llmWinRate = llm?.winRatePct ?? 0;
            const rulesWinRate = rules?.winRatePct ?? 0;

            const llmDD = llm?.maxDrawdownPct ?? 0;
            const rulesDD = rules?.maxDrawdownPct ?? 0;

            // Strict Leader Margin (Always Positive Magnitude)
            const margin = Math.abs(llmReturn - rulesReturn);
            const isLlmAhead = llmReturn > rulesReturn + 0.001;
            const isRulesAhead = rulesReturn > llmReturn + 0.001;

            return (
              <div
                key={pair.id}
                className="cosmic-card rounded-xl p-4 sm:p-5 space-y-3"
              >
                {/* Header: Title, Horizon, and Leader Margin Pill */}
                <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2">
                  <div className="flex items-center gap-2.5">
                    <span className="font-mono text-xs text-zinc-500 font-medium">
                      {idx < 9 ? `0${idx + 1}` : idx + 1}
                    </span>
                    <h3 className="font-sans text-base font-semibold text-white tracking-tight">
                      {pair.philosophyName}
                    </h3>
                    <span className="text-zinc-600">·</span>
                    <span className="text-xs font-mono text-zinc-400">{pair.holdingHorizon}</span>
                  </div>

                  {/* Categorical Leader Pill */}
                  <div>
                    {isLlmAhead ? (
                      <span className="px-2.5 py-0.5 rounded text-xs font-mono font-medium border border-amber-500/30 text-amber-300 bg-amber-500/10">
                        LLM leads +{margin.toFixed(2)}%
                      </span>
                    ) : isRulesAhead ? (
                      <span className="px-2.5 py-0.5 rounded text-xs font-mono font-medium border border-slate-600/40 text-slate-300 bg-slate-500/10">
                        Rules leads +{margin.toFixed(2)}%
                      </span>
                    ) : (
                      <span className="px-2.5 py-0.5 rounded text-xs font-mono font-medium border border-white/10 text-zinc-400 bg-white/5">
                        Tied (0.00%)
                      </span>
                    )}
                  </div>
                </div>

                {/* Seamless Empirical Hypothesis Line (No Jarring Background Box) */}
                <div className="text-xs sm:text-[13px] text-zinc-300 font-sans leading-relaxed flex items-baseline gap-2">
                  <Target className="w-3.5 h-3.5 text-zinc-500 self-center flex-shrink-0" />
                  <span>
                    <strong className="text-zinc-400 font-mono text-[10px] uppercase tracking-wider mr-1.5 font-semibold">
                      Hypothesis:
                    </strong>
                    {pair.coreHypothesis}
                  </span>
                </div>

                {/* Paired Two-Row Table: Generous Padding, Crisp Fonts, Zero Redundant Heavy Headers */}
                <div className="overflow-x-auto rounded-lg border border-white/[0.06] bg-[#1E1E1E]">
                  <table className="w-full text-left border-collapse">
                    <tbody className="divide-y divide-white/[0.04] text-sm font-sans">
                      {/* Row 1: LLM Strategy */}
                      <tr className="hover:bg-white/[0.025] transition-colors">
                        <td className="py-3 px-4 min-w-[220px]">
                          <div className="flex items-center gap-2.5">
                            <Link
                              to={`/portfolio/${llm?.id || pair.llmId}`}
                              className="font-sans font-medium text-[14px] sm:text-[15px] text-white hover:text-amber-300 transition-colors truncate max-w-[200px]"
                            >
                              {pair.llmDisplayName}
                            </Link>
                            <span className="px-1.5 py-0.5 text-[10px] font-mono tracking-wider border border-amber-500/30 text-amber-300 bg-amber-500/10 rounded font-medium flex-shrink-0">
                              LLM
                            </span>
                          </div>
                        </td>

                        <td className="py-3 px-4 text-right font-mono text-sm sm:text-[15px] tabular-nums min-w-[120px]">
                          <span
                            className={
                              llmReturn > 0
                                ? 'text-emerald-400 font-medium'
                                : llmReturn < 0
                                ? 'text-rose-400 font-medium'
                                : 'text-zinc-300 font-normal'
                            }
                          >
                            {formatPct(llmReturn)}
                          </span>
                        </td>

                        <td className="py-3 px-4 text-right font-mono text-sm sm:text-[15px] tabular-nums min-w-[120px]">
                          <span
                            className={
                              llmAlpha > 0
                                ? 'text-emerald-400 font-medium'
                                : llmAlpha < 0
                                ? 'text-rose-400 font-medium'
                                : 'text-zinc-400 font-normal'
                            }
                          >
                            {formatPct(llmAlpha)}
                          </span>
                        </td>

                        <td className="py-3 px-4 text-right font-mono text-sm sm:text-[15px] tabular-nums min-w-[90px]">
                          <span
                            className={
                              llmSharpe >= 1.0
                                ? 'text-emerald-400 font-medium'
                                : llmSharpe < 0
                                ? 'text-rose-400 font-medium'
                                : 'text-zinc-300 font-normal'
                            }
                          >
                            {llmSharpe.toFixed(2)}
                          </span>
                        </td>

                        <td className="py-3 px-4 text-right font-mono text-sm sm:text-[15px] tabular-nums min-w-[90px]">
                          <span
                            className={
                              llmDD >= 15.0
                                ? 'text-rose-400 font-medium'
                                : 'text-zinc-400 font-normal'
                            }
                          >
                            {formatPct(llmDD, false)}
                          </span>
                        </td>

                        <td className="py-3 px-4 text-right font-mono text-sm sm:text-[15px] tabular-nums min-w-[100px]">
                          <span
                            className={
                              llmWinRate >= 50.0
                                ? 'text-emerald-400 font-medium'
                                : llmWinRate < 40.0 && llmWinRate > 0
                                ? 'text-rose-400 font-medium'
                                : 'text-zinc-300 font-normal'
                            }
                          >
                            {formatPct(llmWinRate, false)}
                          </span>
                        </td>
                      </tr>

                      {/* Row 2: Rules Strategy Baseline */}
                      <tr className="hover:bg-white/[0.025] transition-colors bg-white/[0.015]">
                        <td className="py-3 px-4 min-w-[220px]">
                          <div className="flex items-center gap-2.5">
                            <Link
                              to={`/portfolio/${rules?.id || pair.rulesId}`}
                              className="font-sans font-medium text-[14px] sm:text-[15px] text-zinc-300 hover:text-white transition-colors truncate max-w-[200px]"
                            >
                              {pair.rulesDisplayName}
                            </Link>
                            <span className="px-1.5 py-0.5 text-[10px] font-mono tracking-wider border border-slate-600/40 text-slate-300 bg-slate-500/10 rounded font-medium flex-shrink-0">
                              Rules
                            </span>
                          </div>
                        </td>

                        <td className="py-3 px-4 text-right font-mono text-sm sm:text-[15px] tabular-nums min-w-[120px]">
                          <span
                            className={
                              rulesReturn > 0
                                ? 'text-emerald-400 font-medium'
                                : rulesReturn < 0
                                ? 'text-rose-400 font-medium'
                                : 'text-zinc-300 font-normal'
                            }
                          >
                            {formatPct(rulesReturn)}
                          </span>
                        </td>

                        <td className="py-3 px-4 text-right font-mono text-sm sm:text-[15px] tabular-nums min-w-[120px]">
                          <span
                            className={
                              rulesAlpha > 0
                                ? 'text-emerald-400 font-medium'
                                : rulesAlpha < 0
                                ? 'text-rose-400 font-medium'
                                : 'text-zinc-400 font-normal'
                            }
                          >
                            {formatPct(rulesAlpha)}
                          </span>
                        </td>

                        <td className="py-3 px-4 text-right font-mono text-sm sm:text-[15px] tabular-nums min-w-[90px]">
                          <span
                            className={
                              rulesSharpe >= 1.0
                                ? 'text-emerald-400 font-medium'
                                : rulesSharpe < 0
                                ? 'text-rose-400 font-medium'
                                : 'text-zinc-300 font-normal'
                            }
                          >
                            {rulesSharpe.toFixed(2)}
                          </span>
                        </td>

                        <td className="py-3 px-4 text-right font-mono text-sm sm:text-[15px] tabular-nums min-w-[90px]">
                          <span
                            className={
                              rulesDD >= 15.0
                                ? 'text-rose-400 font-medium'
                                : 'text-zinc-400 font-normal'
                            }
                          >
                            {formatPct(rulesDD, false)}
                          </span>
                        </td>

                        <td className="py-3 px-4 text-right font-mono text-sm sm:text-[15px] tabular-nums min-w-[100px]">
                          <span
                            className={
                              rulesWinRate >= 50.0
                                ? 'text-emerald-400 font-medium'
                                : rulesWinRate < 40.0 && rulesWinRate > 0
                                ? 'text-rose-400 font-medium'
                                : 'text-zinc-300 font-normal'
                            }
                          >
                            {formatPct(rulesWinRate, false)}
                          </span>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>

              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
