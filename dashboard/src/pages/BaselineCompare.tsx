import { useState, useEffect } from 'react';
import {
  Scale,
  TrendingUp,
  Brain,
  Cpu,
} from 'lucide-react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
} from 'recharts';
import type { BaselineComparison } from '../types';
import { apiService } from '../services/api';
import { formatPaiseToRupees, formatPct } from '../utils/formatters';
import SmallSampleNotice from '../components/SmallSampleNotice';

export default function BaselineCompare() {
  const [data, setData] = useState<BaselineComparison | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const comp = await apiService.getBaselineComparison();
        setData(comp);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading || !data) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-12 flex justify-center items-center">
        <div className="flex items-center gap-3 text-stone-500 font-mono text-sm">
          <div className="w-4 h-4 border-2 border-amber-500 border-t-transparent rounded-full animate-spin" />
          <span>Loading paired comparison experiment data...</span>
        </div>
      </div>
    );
  }

  const chartData = data.horizonReturns.map((hr) => ({
    horizon: `${hr.horizonDays}d`,
    'LLM Simons (BUY)': hr.llmSimonsBuyAvgPct,
    'LLM Simons (HOLD)': hr.llmSimonsHoldAvgPct,
    'Rules Simons (BUY)': hr.rulesSimonsBuyAvgPct,
    'Nifty 500 Index': hr.nifty500AvgPct,
  }));

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8 animate-fade-in">
      {/* Page Header */}
      <div className="border-b border-stone-200 dark:border-stone-800 pb-6">
        <div className="flex items-center gap-2 text-xs font-mono text-amber-600 dark:text-amber-400 uppercase tracking-wider mb-1">
          <Scale className="w-3.5 h-3.5" />
          <span>Core Empirical Research Experiment</span>
        </div>
        <h1 className="text-3xl font-bold tracking-tight text-stone-900 dark:text-stone-100 font-serif">
          LLM Simons vs. Rules Baseline vs. Nifty 500
        </h1>
        <p className="text-sm text-stone-500 dark:text-stone-400 mt-1 max-w-3xl leading-relaxed">
          Evaluating the central research question: <em>Does adding an LLM cognitive decision layer produce measurable value-add over identical deterministic rules and the market benchmark?</em> Both agents trade the exact same Stage-3 candidate funnel through the same simulated broker.
        </p>
      </div>

      <SmallSampleNotice closedTradesCount={data.llmSimons.trades} threshold={30} />

      {/* Head-to-Head Triple Comparison Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Card 1: LLM Simons */}
        <div className="p-6 rounded-xl bg-white dark:bg-stone-900 border-2 border-blue-500/30 dark:border-blue-500/20 shadow-xs relative">
          <div className="flex justify-between items-center mb-3">
            <span className="flex items-center gap-2 font-semibold text-stone-900 dark:text-stone-100 font-serif text-lg">
              <Brain className="w-5 h-5 text-blue-600 dark:text-blue-400" />
              <span>Simons (LLM)</span>
            </span>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-100 text-blue-800 dark:bg-blue-950/60 dark:text-blue-300 font-semibold">
              TEST SUBJECT
            </span>
          </div>
          <div className="text-3xl font-bold font-mono text-blue-600 dark:text-blue-400 mb-4">
            {formatPct(data.llmSimons.returnPct)}
          </div>
          <div className="space-y-2 text-xs font-mono text-stone-600 dark:text-stone-400 border-t border-stone-100 dark:border-stone-800 pt-3">
            <div className="flex justify-between">
              <span>Total NAV:</span>
              <span className="font-semibold text-stone-900 dark:text-stone-100">{formatPaiseToRupees(data.llmSimons.navPaise)}</span>
            </div>
            <div className="flex justify-between">
              <span>Sharpe Ratio:</span>
              <span className="font-semibold text-stone-900 dark:text-stone-100">{data.llmSimons.sharpe.toFixed(2)}</span>
            </div>
            <div className="flex justify-between">
              <span>Max Drawdown:</span>
              <span className="font-semibold text-rose-600">-{data.llmSimons.maxDrawdownPct.toFixed(2)}%</span>
            </div>
            <div className="flex justify-between">
              <span>Win Rate:</span>
              <span className="font-semibold text-stone-900 dark:text-stone-100">{data.llmSimons.winRatePct.toFixed(1)}%</span>
            </div>
            <div className="flex justify-between">
              <span>Faithfulness Rate:</span>
              <span className="font-semibold text-purple-600">{data.llmSimons.faithfulnessRatePct.toFixed(1)}%</span>
            </div>
          </div>
        </div>

        {/* Card 2: Rules Baseline */}
        <div className="p-6 rounded-xl bg-white dark:bg-stone-900 border-2 border-stone-300 dark:border-stone-700 shadow-xs relative">
          <div className="flex justify-between items-center mb-3">
            <span className="flex items-center gap-2 font-semibold text-stone-900 dark:text-stone-100 font-serif text-lg">
              <Cpu className="w-5 h-5 text-stone-600 dark:text-stone-400" />
              <span>Simons (Rules Only)</span>
            </span>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-stone-100 text-stone-700 dark:bg-stone-800 dark:text-stone-300 font-semibold">
              CONTROL AGENT
            </span>
          </div>
          <div className="text-3xl font-bold font-mono text-stone-700 dark:text-stone-300 mb-4">
            {formatPct(data.rulesSimons.returnPct)}
          </div>
          <div className="space-y-2 text-xs font-mono text-stone-600 dark:text-stone-400 border-t border-stone-100 dark:border-stone-800 pt-3">
            <div className="flex justify-between">
              <span>Total NAV:</span>
              <span className="font-semibold text-stone-900 dark:text-stone-100">{formatPaiseToRupees(data.rulesSimons.navPaise)}</span>
            </div>
            <div className="flex justify-between">
              <span>Sharpe Ratio:</span>
              <span className="font-semibold text-stone-900 dark:text-stone-100">{data.rulesSimons.sharpe.toFixed(2)}</span>
            </div>
            <div className="flex justify-between">
              <span>Max Drawdown:</span>
              <span className="font-semibold text-rose-600">-{data.rulesSimons.maxDrawdownPct.toFixed(2)}%</span>
            </div>
            <div className="flex justify-between">
              <span>Win Rate:</span>
              <span className="font-semibold text-stone-900 dark:text-stone-100">{data.rulesSimons.winRatePct.toFixed(1)}%</span>
            </div>
            <div className="flex justify-between">
              <span>Faithfulness Rate:</span>
              <span className="font-semibold text-stone-500">100.0% (Rules)</span>
            </div>
          </div>
        </div>

        {/* Card 3: Nifty 500 Index */}
        <div className="p-6 rounded-xl bg-white dark:bg-stone-900 border-2 border-stone-200 dark:border-stone-800 shadow-xs relative">
          <div className="flex justify-between items-center mb-3">
            <span className="flex items-center gap-2 font-semibold text-stone-900 dark:text-stone-100 font-serif text-lg">
              <TrendingUp className="w-5 h-5 text-stone-500" />
              <span>Nifty 500 Index</span>
            </span>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-stone-100 text-stone-600 dark:bg-stone-800 dark:text-stone-400 font-semibold">
              MARKET BENCHMARK
            </span>
          </div>
          <div className="text-3xl font-bold font-mono text-stone-600 dark:text-stone-400 mb-4">
            {formatPct(data.nifty500.returnPct)}
          </div>
          <div className="space-y-2 text-xs font-mono text-stone-600 dark:text-stone-400 border-t border-stone-100 dark:border-stone-800 pt-3">
            <div className="flex justify-between">
              <span>Benchmark NAV:</span>
              <span className="font-semibold text-stone-900 dark:text-stone-100">{formatPaiseToRupees(data.nifty500.benchmarkNavPaise)}</span>
            </div>
            <div className="flex justify-between">
              <span>Max Drawdown:</span>
              <span className="font-semibold text-rose-600">-{data.nifty500.maxDrawdownPct.toFixed(2)}%</span>
            </div>
            <div className="flex justify-between">
              <span>Trading Friction:</span>
              <span className="font-semibold text-stone-500">0.00% (Passive)</span>
            </div>
            <div className="flex justify-between">
              <span>LLM Alpha vs Index:</span>
              <span className="font-semibold text-emerald-600">
                {formatPct(data.llmSimons.returnPct - data.nifty500.returnPct)}
              </span>
            </div>
            <div className="flex justify-between">
              <span>Rules Alpha vs Index:</span>
              <span className="font-semibold text-stone-700 dark:text-stone-300">
                {formatPct(data.rulesSimons.returnPct - data.nifty500.returnPct)}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Candidate Selection Alpha Section: Forward Return Analysis */}
      <div className="bg-white dark:bg-stone-900 rounded-xl border border-stone-200 dark:border-stone-800 p-6 shadow-sm space-y-4">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-base font-semibold text-stone-900 dark:text-stone-100 font-serif">
              Forward Return Analysis: BUY Selection vs HOLD Rejection
            </h3>
            <span className="text-xs px-2 py-0.5 rounded font-mono bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300 font-semibold">
              Alpha Spread: +{data.candidateSelectionAlpha.toFixed(2)}%
            </span>
          </div>
          <p className="text-xs text-stone-500 mt-1">
            Because closed trades are naturally few during short live pilots, forward return evaluation tracks what happens to <em>all</em> candidate decisions (both chosen BUY orders and rejected HOLDs) across 1, 5, 10, 20, and 60 trading days.
          </p>
        </div>

        {/* Recharts Bar Chart */}
        <div className="w-full h-80 pt-2">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" strokeOpacity={0.6} />
              <XAxis dataKey="horizon" stroke="#64748b" fontSize={11} />
              <YAxis stroke="#64748b" fontSize={11} tickFormatter={(v) => `${v}%`} />
              <Tooltip
                formatter={(value: unknown) => [`${Number(value).toFixed(2)}%`, '']}
                contentStyle={{ backgroundColor: '#1e293b', borderColor: '#334155', color: '#fff', fontSize: '11px', borderRadius: '8px' }}
              />
              <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }} />
              <Bar dataKey="LLM Simons (BUY)" fill="#2563eb" radius={[4, 4, 0, 0]} />
              <Bar dataKey="LLM Simons (HOLD)" fill="#94a3b8" radius={[4, 4, 0, 0]} />
              <Bar dataKey="Rules Simons (BUY)" fill="#dc2626" radius={[4, 4, 0, 0]} />
              <Bar dataKey="Nifty 500 Index" fill="#64748b" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Tabular Horizon Breakdown */}
        <div className="overflow-x-auto pt-2">
          <table className="w-full text-left text-xs font-mono text-stone-700 dark:text-stone-300">
            <thead className="bg-stone-50 dark:bg-stone-800/60 uppercase font-semibold text-[11px] text-stone-500">
              <tr>
                <th className="py-2.5 px-3">Horizon</th>
                <th className="py-2.5 px-3 text-right">LLM Simons BUY</th>
                <th className="py-2.5 px-3 text-right">LLM Simons HOLD</th>
                <th className="py-2.5 px-3 text-right">Selection Alpha (BUY - HOLD)</th>
                <th className="py-2.5 px-3 text-right">Rules Simons BUY</th>
                <th className="py-2.5 px-3 text-right">Nifty 500 Return</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-stone-100 dark:divide-stone-800">
              {data.horizonReturns.map((hr) => (
                <tr key={hr.horizonDays} className="hover:bg-stone-50/60 dark:hover:bg-stone-800/40">
                  <td className="py-2.5 px-3 font-semibold">{hr.horizonDays} Trading Days</td>
                  <td className="py-2.5 px-3 text-right text-blue-600 font-semibold">{formatPct(hr.llmSimonsBuyAvgPct)}</td>
                  <td className="py-2.5 px-3 text-right text-stone-500">{formatPct(hr.llmSimonsHoldAvgPct)}</td>
                  <td className="py-2.5 px-3 text-right text-emerald-600 font-bold">+{hr.selectionAlphaPct.toFixed(2)}%</td>
                  <td className="py-2.5 px-3 text-right text-stone-700 dark:text-stone-300">{formatPct(hr.rulesSimonsBuyAvgPct)}</td>
                  <td className="py-2.5 px-3 text-right text-stone-500">{formatPct(hr.nifty500AvgPct)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
