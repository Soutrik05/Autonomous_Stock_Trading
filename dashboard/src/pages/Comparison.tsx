import { useState, useEffect } from 'react';
import {
  Scale,
  Brain,
  Cpu,
  TrendingUp,
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

export default function Comparison() {
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
      <div className="max-w-7xl mx-auto px-4 py-16 flex justify-center items-center">
        <div className="flex items-center gap-3 text-stone-500 font-mono text-sm">
          <div className="w-4 h-4 border-2 border-amber-600 border-t-transparent rounded-full animate-spin" />
          <span>Loading paired comparison experiment...</span>
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
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8 animate-fade-in font-sans">
      {/* Header */}
      <div className="border-b border-[#E5E2D9] pb-6">
        <div className="flex items-center gap-2 text-xs font-mono text-[#D97706] uppercase tracking-wider mb-1 font-semibold">
          <Scale className="w-3.5 h-3.5" />
          <span>Paired Experimental Benchmark</span>
        </div>
        <h1 className="text-3xl font-serif font-bold text-[#111827]">
          Cognitive Alpha vs. Deterministic Rules
        </h1>
        <p className="text-sm text-[#4B5563] mt-1 max-w-3xl leading-relaxed">
          Evaluating the central research hypothesis: <em>Does an LLM cognitive layer add measurable value over identical hard-coded rules and the market index?</em> Both strategies evaluate the exact same candidate list through the same broker.
        </p>
      </div>

      <SmallSampleNotice closedTradesCount={data.llmSimons.trades} threshold={30} />

      {/* Triple Head-to-Head Comparison Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {/* Card 1: LLM Simons */}
        <div className="porcelain-card p-6 border-blue-400/80 ring-1 ring-blue-400/20 bg-white space-y-4">
          <div className="flex justify-between items-center">
            <span className="flex items-center gap-2 font-serif font-bold text-lg text-[#111827]">
              <Brain className="w-5 h-5 text-blue-600" />
              <span>Simons (LLM)</span>
            </span>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-100 text-blue-800 font-bold">
              LLM
            </span>
          </div>

          <div className="text-3xl font-bold font-mono text-blue-600">
            {formatPct(data.llmSimons.returnPct)}
          </div>

          <div className="space-y-2 text-xs font-mono text-[#4B5563] border-t border-[#EDEAE2] pt-3">
            <div className="flex justify-between">
              <span>Total NAV:</span>
              <span className="font-semibold text-[#111827]">{formatPaiseToRupees(data.llmSimons.navPaise)}</span>
            </div>
            <div className="flex justify-between">
              <span>Sharpe Ratio:</span>
              <span className="font-semibold text-[#111827]">{data.llmSimons.sharpe.toFixed(2)}</span>
            </div>
            <div className="flex justify-between">
              <span>Max Drawdown:</span>
              <span className="font-semibold text-rose-600">-{data.llmSimons.maxDrawdownPct.toFixed(2)}%</span>
            </div>
            <div className="flex justify-between">
              <span>Win Rate:</span>
              <span className="font-semibold text-[#111827]">{data.llmSimons.winRatePct.toFixed(1)}%</span>
            </div>
            <div className="flex justify-between">
              <span>Faithfulness Rate:</span>
              <span className="font-semibold text-purple-700">{data.llmSimons.faithfulnessRatePct.toFixed(1)}%</span>
            </div>
          </div>
        </div>

        {/* Card 2: Rules Simons */}
        <div className="porcelain-card p-6 bg-white space-y-4">
          <div className="flex justify-between items-center">
            <span className="flex items-center gap-2 font-serif font-bold text-lg text-[#111827]">
              <Cpu className="w-5 h-5 text-stone-500" />
              <span>Simons (Rules Only)</span>
            </span>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-stone-100 text-stone-700 font-bold">
              RULES
            </span>
          </div>

          <div className="text-3xl font-bold font-mono text-[#111827]">
            {formatPct(data.rulesSimons.returnPct)}
          </div>

          <div className="space-y-2 text-xs font-mono text-[#4B5563] border-t border-[#EDEAE2] pt-3">
            <div className="flex justify-between">
              <span>Total NAV:</span>
              <span className="font-semibold text-[#111827]">{formatPaiseToRupees(data.rulesSimons.navPaise)}</span>
            </div>
            <div className="flex justify-between">
              <span>Sharpe Ratio:</span>
              <span className="font-semibold text-[#111827]">{data.rulesSimons.sharpe.toFixed(2)}</span>
            </div>
            <div className="flex justify-between">
              <span>Max Drawdown:</span>
              <span className="font-semibold text-rose-600">-{data.rulesSimons.maxDrawdownPct.toFixed(2)}%</span>
            </div>
            <div className="flex justify-between">
              <span>Win Rate:</span>
              <span className="font-semibold text-[#111827]">{data.rulesSimons.winRatePct.toFixed(1)}%</span>
            </div>
            <div className="flex justify-between">
              <span>Faithfulness Rate:</span>
              <span className="font-semibold text-[#9CA3AF]">100.0% (Rules)</span>
            </div>
          </div>
        </div>

        {/* Card 3: Nifty 500 Index */}
        <div className="porcelain-card p-6 bg-white space-y-4">
          <div className="flex justify-between items-center">
            <span className="flex items-center gap-2 font-serif font-bold text-lg text-[#111827]">
              <TrendingUp className="w-5 h-5 text-stone-400" />
              <span>Nifty 500 Index</span>
            </span>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-stone-100 text-[#4B5563] font-bold">
              BENCHMARK
            </span>
          </div>

          <div className="text-3xl font-bold font-mono text-[#4B5563]">
            {formatPct(data.nifty500.returnPct)}
          </div>

          <div className="space-y-2 text-xs font-mono text-[#4B5563] border-t border-[#EDEAE2] pt-3">
            <div className="flex justify-between">
              <span>Benchmark NAV:</span>
              <span className="font-semibold text-[#111827]">{formatPaiseToRupees(data.nifty500.benchmarkNavPaise)}</span>
            </div>
            <div className="flex justify-between">
              <span>Max Drawdown:</span>
              <span className="font-semibold text-rose-600">-{data.nifty500.maxDrawdownPct.toFixed(2)}%</span>
            </div>
            <div className="flex justify-between">
              <span>LLM Alpha vs Index:</span>
              <span className="font-bold text-emerald-600">
                +{formatPct(data.llmSimons.returnPct - data.nifty500.returnPct)}
              </span>
            </div>
            <div className="flex justify-between">
              <span>Rules Alpha vs Index:</span>
              <span className="font-semibold text-[#111827]">
                {formatPct(data.rulesSimons.returnPct - data.nifty500.returnPct)}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Candidate Selection Alpha: Multi-Horizon Forward Return Analysis */}
      <div className="porcelain-card p-6 space-y-4">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2">
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-base font-serif font-bold text-[#111827]">
                Candidate Selection Alpha: BUY vs. HOLD Forward Returns
              </h3>
              <span className="px-2 py-0.5 rounded font-mono text-xs bg-emerald-100 text-emerald-800 font-bold">
                Alpha Spread: +{data.candidateSelectionAlpha.toFixed(2)}%
              </span>
            </div>
            <p className="text-xs text-[#4B5563] mt-1">
              Tracks what happens to candidates selected for BUY versus candidates rejected as HOLD across 1, 5, 10, 20, and 60 trading days forward.
            </p>
          </div>
        </div>

        {/* Recharts Bar Chart */}
        <div className="w-full h-80 pt-2">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#E5E2D9" strokeOpacity={0.7} />
              <XAxis dataKey="horizon" stroke="#9CA3AF" fontSize={11} />
              <YAxis stroke="#9CA3AF" fontSize={11} tickFormatter={(v) => `${v}%`} />
              <Tooltip
                formatter={(value: unknown) => [`${Number(value).toFixed(2)}%`, '']}
                contentStyle={{ backgroundColor: '#FFFFFF', borderColor: '#E5E2D9', color: '#111827', fontSize: '11px', borderRadius: '8px' }}
              />
              <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }} />
              <Bar dataKey="LLM Simons (BUY)" fill="#2563EB" radius={[4, 4, 0, 0]} />
              <Bar dataKey="LLM Simons (HOLD)" fill="#94A3B8" radius={[4, 4, 0, 0]} />
              <Bar dataKey="Rules Simons (BUY)" fill="#DC2626" radius={[4, 4, 0, 0]} />
              <Bar dataKey="Nifty 500 Index" fill="#64748B" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Tabular Horizon Breakdown */}
        <div className="overflow-x-auto pt-2">
          <table className="w-full text-left text-xs font-mono text-[#111827]">
            <thead className="bg-[#F4F2EC] uppercase text-[11px] text-[#4B5563] border-b border-[#E5E2D9]">
              <tr>
                <th className="py-2.5 px-3">Horizon</th>
                <th className="py-2.5 px-3 text-right">LLM Simons BUY</th>
                <th className="py-2.5 px-3 text-right">LLM Simons HOLD</th>
                <th className="py-2.5 px-3 text-right">Selection Alpha (BUY - HOLD)</th>
                <th className="py-2.5 px-3 text-right">Rules Simons BUY</th>
                <th className="py-2.5 px-3 text-right">Nifty 500 Return</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#EDEAE2]">
              {data.horizonReturns.map((hr) => (
                <tr key={hr.horizonDays} className="hover:bg-[#F7F5EE]">
                  <td className="py-2.5 px-3 font-semibold">{hr.horizonDays} Trading Days</td>
                  <td className="py-2.5 px-3 text-right text-blue-600 font-bold">{formatPct(hr.llmSimonsBuyAvgPct)}</td>
                  <td className="py-2.5 px-3 text-right text-[#4B5563]">{formatPct(hr.llmSimonsHoldAvgPct)}</td>
                  <td className="py-2.5 px-3 text-right text-emerald-600 font-bold">+{hr.selectionAlphaPct.toFixed(2)}%</td>
                  <td className="py-2.5 px-3 text-right text-[#111827]">{formatPct(hr.rulesSimonsBuyAvgPct)}</td>
                  <td className="py-2.5 px-3 text-right text-[#9CA3AF]">{formatPct(hr.nifty500AvgPct)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
