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
    const handleSync = () => load();
    window.addEventListener('mock_mode_changed', handleSync);
    return () => window.removeEventListener('mock_mode_changed', handleSync);
  }, []);

  if (loading || !data) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-24 flex justify-center items-center">
        <div className="flex items-center gap-3 text-slate-400 font-mono text-sm">
          <div className="w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
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
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6 animate-fade-in font-sans">
      {/* Header */}
      <div className="border-b border-white/[0.08] pb-4 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2">
        <div>
          <div className="flex items-center gap-2 text-xs font-mono text-zinc-400 mb-1 font-semibold uppercase tracking-wider">
            <Scale className="w-3.5 h-3.5 text-blue-400" />
            <span>Paired Experimental Benchmark</span>
          </div>
          <h1 className="font-serif text-3xl sm:text-4xl font-normal tracking-tight text-white">
            Cognitive Alpha vs. Deterministic Rules
          </h1>
        </div>
        <div className="text-xs font-mono text-zinc-400">
          Hypothesis: LLM vs Rules (Simons Control)
        </div>
      </div>

      <SmallSampleNotice closedTradesCount={data.llmSimons.trades} threshold={30} />

      {/* Triple Head-to-Head Comparison Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {/* Card 1: LLM Simons */}
        <div className="arena-glow-card p-6 border-blue-500/30 bg-blue-500/5 space-y-4">
          <div className="flex justify-between items-center">
            <span className="flex items-center gap-2 font-bold text-lg text-white">
              <Brain className="w-4 h-4 text-blue-400" />
              <span>Simons (LLM)</span>
            </span>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 border border-blue-500/40">
              LLM Persona
            </span>
          </div>

          <div className="text-3xl font-bold font-mono text-blue-400">
            {formatPct(data.llmSimons.returnPct)}
          </div>

          <div className="space-y-2 text-xs font-mono text-slate-400 border-t border-white/10 pt-3.5">
            <div className="flex justify-between">
              <span>Total NAV:</span>
              <span className="font-semibold text-white">{formatPaiseToRupees(data.llmSimons.navPaise)}</span>
            </div>
            <div className="flex justify-between">
              <span>Sharpe Ratio:</span>
              <span className="font-semibold text-white">{data.llmSimons.sharpe.toFixed(2)}</span>
            </div>
            <div className="flex justify-between">
              <span>Max Drawdown:</span>
              <span className="font-semibold text-rose-400">-{data.llmSimons.maxDrawdownPct.toFixed(2)}%</span>
            </div>
            <div className="flex justify-between">
              <span>Win Rate:</span>
              <span className="font-semibold text-white">{data.llmSimons.winRatePct.toFixed(1)}%</span>
            </div>
            <div className="flex justify-between">
              <span>Faithfulness Rate:</span>
              <span className="font-semibold text-purple-400">{data.llmSimons.faithfulnessRatePct.toFixed(1)}%</span>
            </div>
          </div>
        </div>

        {/* Card 2: Rules Simons */}
        <div className="arena-glass p-6 space-y-4">
          <div className="flex justify-between items-center">
            <span className="flex items-center gap-2 font-bold text-lg text-white">
              <Cpu className="w-4 h-4 text-slate-400" />
              <span>Simons (Rules Only)</span>
            </span>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-white/5 text-slate-400 border border-white/10">
              Rules Control
            </span>
          </div>

          <div className="text-3xl font-extrabold font-mono text-white">
            {formatPct(data.rulesSimons.returnPct)}
          </div>

          <div className="space-y-2 text-xs font-mono text-slate-400 border-t border-white/10 pt-3.5">
            <div className="flex justify-between">
              <span>Total NAV:</span>
              <span className="font-semibold text-white">{formatPaiseToRupees(data.rulesSimons.navPaise)}</span>
            </div>
            <div className="flex justify-between">
              <span>Sharpe Ratio:</span>
              <span className="font-semibold text-white">{data.rulesSimons.sharpe.toFixed(2)}</span>
            </div>
            <div className="flex justify-between">
              <span>Max Drawdown:</span>
              <span className="font-semibold text-rose-400">-{data.rulesSimons.maxDrawdownPct.toFixed(2)}%</span>
            </div>
            <div className="flex justify-between">
              <span>Win Rate:</span>
              <span className="font-semibold text-white">{data.rulesSimons.winRatePct.toFixed(1)}%</span>
            </div>
            <div className="flex justify-between">
              <span>Faithfulness Rate:</span>
              <span className="font-semibold text-slate-500">100.0% (Deterministic)</span>
            </div>
          </div>
        </div>

        {/* Card 3: Nifty 500 Index */}
        <div className="arena-glass p-6 space-y-4">
          <div className="flex justify-between items-center">
            <span className="flex items-center gap-2 font-bold text-lg text-white">
              <TrendingUp className="w-4 h-4 text-slate-500" />
              <span>Nifty 500 Index</span>
            </span>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-white/5 text-slate-400 border border-white/10">
              Benchmark
            </span>
          </div>

          <div className="text-3xl font-extrabold font-mono text-slate-300">
            {formatPct(data.nifty500.returnPct)}
          </div>

          <div className="space-y-2 text-xs font-mono text-slate-400 border-t border-white/10 pt-3.5">
            <div className="flex justify-between">
              <span>Benchmark NAV:</span>
              <span className="font-semibold text-white">{formatPaiseToRupees(data.nifty500.benchmarkNavPaise)}</span>
            </div>
            <div className="flex justify-between">
              <span>Max Drawdown:</span>
              <span className="font-semibold text-rose-400">-{data.nifty500.maxDrawdownPct.toFixed(2)}%</span>
            </div>
            <div className="flex justify-between">
              <span>LLM Alpha vs Index:</span>
              <span className="font-bold text-emerald-400">
                +{formatPct(data.llmSimons.returnPct - data.nifty500.returnPct)}
              </span>
            </div>
            <div className="flex justify-between">
              <span>Rules Alpha vs Index:</span>
              <span className="font-semibold text-white">
                {formatPct(data.rulesSimons.returnPct - data.nifty500.returnPct)}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Candidate Selection Alpha: Multi-Horizon Forward Return Analysis */}
      <div className="arena-glass p-6 sm:p-7 space-y-5">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
          <div>
            <div className="flex items-center gap-2.5">
              <h3 className="text-base sm:text-lg font-bold text-white">
                Candidate Selection Alpha: BUY vs. HOLD Forward Returns
              </h3>
              <span className="px-2.5 py-0.5 rounded font-mono text-xs bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 font-semibold">
                Alpha Spread: +{data.candidateSelectionAlpha.toFixed(2)}%
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-1">
              Tracks forward return trajectories of candidates selected for BUY versus candidates rejected as HOLD across 1, 5, 10, 20, and 60 trading days.
            </p>
          </div>
        </div>

        {/* Recharts Bar Chart */}
        <div className="w-full h-80 pt-2 min-h-[300px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
              <XAxis dataKey="horizon" stroke="#64748B" fontSize={11} />
              <YAxis stroke="#64748B" fontSize={11} tickFormatter={(v) => `${v}%`} />
              <Tooltip
                formatter={(value: unknown) => [`${Number(value).toFixed(2)}%`, '']}
                contentStyle={{ backgroundColor: '#0B0F19', borderColor: 'rgba(255,255,255,0.15)', color: '#FFFFFF', fontSize: '11px', borderRadius: '8px' }}
              />
              <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }} />
              <Bar dataKey="LLM Simons (BUY)" fill="#06B6D4" radius={[4, 4, 0, 0]} />
              <Bar dataKey="LLM Simons (HOLD)" fill="#64748B" radius={[4, 4, 0, 0]} />
              <Bar dataKey="Rules Simons (BUY)" fill="#3B82F6" radius={[4, 4, 0, 0]} />
              <Bar dataKey="Nifty 500 Index" fill="#94A3B8" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Tabular Horizon Breakdown */}
        <div className="overflow-x-auto pt-2">
          <table className="w-full text-left text-xs font-mono text-slate-200">
            <thead className="bg-white/[0.02] text-[11px] text-slate-400 border-b border-white/10">
              <tr>
                <th className="py-2.5 px-3 font-semibold">Horizon</th>
                <th className="py-2.5 px-3 text-right font-semibold">LLM Simons BUY</th>
                <th className="py-2.5 px-3 text-right font-semibold">LLM Simons HOLD</th>
                <th className="py-2.5 px-3 text-right font-semibold">Selection Alpha (BUY - HOLD)</th>
                <th className="py-2.5 px-3 text-right font-semibold">Rules Simons BUY</th>
                <th className="py-2.5 px-3 text-right font-semibold">Nifty 500 Return</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {data.horizonReturns.map((hr) => (
                <tr key={hr.horizonDays} className="hover:bg-white/[0.04] transition-colors">
                  <td className="py-2.5 px-3 font-semibold text-white">{hr.horizonDays} Trading Days</td>
                  <td className="py-2.5 px-3 text-right text-blue-400 font-semibold">{formatPct(hr.llmSimonsBuyAvgPct)}</td>
                  <td className="py-2.5 px-3 text-right text-slate-400">{formatPct(hr.llmSimonsHoldAvgPct)}</td>
                  <td className="py-2.5 px-3 text-right text-emerald-400 font-semibold">+{hr.selectionAlphaPct.toFixed(2)}%</td>
                  <td className="py-2.5 px-3 text-right text-white">{formatPct(hr.rulesSimonsBuyAvgPct)}</td>
                  <td className="py-2.5 px-3 text-right text-slate-500">{formatPct(hr.nifty500AvgPct)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
