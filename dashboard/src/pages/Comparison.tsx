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
        <div className="flex items-center gap-3 text-[#7C8698] font-mono text-sm">
          <div className="w-4 h-4 border-2 border-[#8A7441] border-t-transparent rounded-full animate-spin" />
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
      <div className="border-b border-[#DCD7CC] pb-6">
        <div className="flex items-center gap-1.5 text-xs font-mono text-[#8A7441] mb-1">
          <Scale className="w-3.5 h-3.5" />
          <span>Paired experimental benchmark</span>
        </div>
        <h1 className="text-3xl font-serif font-bold text-[#151B26]">
          Cognitive alpha vs. deterministic rules
        </h1>
        <p className="text-sm text-[#475060] mt-1 max-w-3xl leading-relaxed">
          Evaluating the central research hypothesis: <em>Does an LLM cognitive layer add measurable value over identical hard-coded rules and the market index?</em> Both strategies evaluate the exact same candidate list through the same simulated broker.
        </p>
      </div>

      <SmallSampleNotice closedTradesCount={data.llmSimons.trades} threshold={30} />

      {/* Triple Head-to-Head Comparison Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {/* Card 1: LLM Simons */}
        <div className="ledger-panel p-6 border-[#2A4B7C]/40 bg-white space-y-4">
          <div className="flex justify-between items-center">
            <span className="flex items-center gap-2 font-serif font-bold text-lg text-[#151B26]">
              <Brain className="w-4 h-4 text-[#1E4E8C]" />
              <span>Simons (LLM)</span>
            </span>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded-[2px] bg-[#EDF2F9] text-[#2A4B7C] border border-[#B9C9E1]">
              LLM persona
            </span>
          </div>

          <div className="text-3xl font-bold font-mono text-[#1E4E8C]">
            {formatPct(data.llmSimons.returnPct)}
          </div>

          <div className="space-y-2 text-xs font-mono text-[#475060] border-t border-[#E7E3D9] pt-3">
            <div className="flex justify-between">
              <span>Total NAV:</span>
              <span className="font-semibold text-[#151B26]">{formatPaiseToRupees(data.llmSimons.navPaise)}</span>
            </div>
            <div className="flex justify-between">
              <span>Sharpe ratio:</span>
              <span className="font-semibold text-[#151B26]">{data.llmSimons.sharpe.toFixed(2)}</span>
            </div>
            <div className="flex justify-between">
              <span>Max drawdown:</span>
              <span className="font-semibold text-[#933835]">-{data.llmSimons.maxDrawdownPct.toFixed(2)}%</span>
            </div>
            <div className="flex justify-between">
              <span>Win rate:</span>
              <span className="font-semibold text-[#151B26]">{data.llmSimons.winRatePct.toFixed(1)}%</span>
            </div>
            <div className="flex justify-between">
              <span>Faithfulness rate:</span>
              <span className="font-semibold text-[#2A4B7C]">{data.llmSimons.faithfulnessRatePct.toFixed(1)}%</span>
            </div>
          </div>
        </div>

        {/* Card 2: Rules Simons */}
        <div className="ledger-panel p-6 bg-white space-y-4">
          <div className="flex justify-between items-center">
            <span className="flex items-center gap-2 font-serif font-bold text-lg text-[#151B26]">
              <Cpu className="w-4 h-4 text-[#475060]" />
              <span>Simons (Rules only)</span>
            </span>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded-[2px] bg-[#F6F4EF] text-[#475060] border border-[#DCD7CC]">
              Rules control
            </span>
          </div>

          <div className="text-3xl font-bold font-mono text-[#151B26]">
            {formatPct(data.rulesSimons.returnPct)}
          </div>

          <div className="space-y-2 text-xs font-mono text-[#475060] border-t border-[#E7E3D9] pt-3">
            <div className="flex justify-between">
              <span>Total NAV:</span>
              <span className="font-semibold text-[#151B26]">{formatPaiseToRupees(data.rulesSimons.navPaise)}</span>
            </div>
            <div className="flex justify-between">
              <span>Sharpe ratio:</span>
              <span className="font-semibold text-[#151B26]">{data.rulesSimons.sharpe.toFixed(2)}</span>
            </div>
            <div className="flex justify-between">
              <span>Max drawdown:</span>
              <span className="font-semibold text-[#933835]">-{data.rulesSimons.maxDrawdownPct.toFixed(2)}%</span>
            </div>
            <div className="flex justify-between">
              <span>Win rate:</span>
              <span className="font-semibold text-[#151B26]">{data.rulesSimons.winRatePct.toFixed(1)}%</span>
            </div>
            <div className="flex justify-between">
              <span>Faithfulness rate:</span>
              <span className="font-semibold text-[#7C8698]">100.0% (Deterministic)</span>
            </div>
          </div>
        </div>

        {/* Card 3: Nifty 500 Index */}
        <div className="ledger-panel p-6 bg-white space-y-4">
          <div className="flex justify-between items-center">
            <span className="flex items-center gap-2 font-serif font-bold text-lg text-[#151B26]">
              <TrendingUp className="w-4 h-4 text-[#7C8698]" />
              <span>Nifty 500 index</span>
            </span>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded-[2px] bg-[#F6F4EF] text-[#7C8698] border border-[#DCD7CC]">
              Benchmark
            </span>
          </div>

          <div className="text-3xl font-bold font-mono text-[#475060]">
            {formatPct(data.nifty500.returnPct)}
          </div>

          <div className="space-y-2 text-xs font-mono text-[#475060] border-t border-[#E7E3D9] pt-3">
            <div className="flex justify-between">
              <span>Benchmark NAV:</span>
              <span className="font-semibold text-[#151B26]">{formatPaiseToRupees(data.nifty500.benchmarkNavPaise)}</span>
            </div>
            <div className="flex justify-between">
              <span>Max drawdown:</span>
              <span className="font-semibold text-[#933835]">-{data.nifty500.maxDrawdownPct.toFixed(2)}%</span>
            </div>
            <div className="flex justify-between">
              <span>LLM alpha vs index:</span>
              <span className="font-bold text-[#1E6548]">
                +{formatPct(data.llmSimons.returnPct - data.nifty500.returnPct)}
              </span>
            </div>
            <div className="flex justify-between">
              <span>Rules alpha vs index:</span>
              <span className="font-semibold text-[#151B26]">
                {formatPct(data.rulesSimons.returnPct - data.nifty500.returnPct)}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Candidate Selection Alpha: Multi-Horizon Forward Return Analysis */}
      <div className="chart-frame p-6 space-y-4">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2">
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-base font-serif font-bold text-[#151B26]">
                Candidate selection alpha: BUY vs. HOLD forward returns
              </h3>
              <span className="px-2 py-0.5 rounded-[2px] font-mono text-xs bg-[#EBF5F0] text-[#1E6548] border border-[#A3D4BE] font-medium">
                Alpha spread: +{data.candidateSelectionAlpha.toFixed(2)}%
              </span>
            </div>
            <p className="text-xs text-[#7C8698] mt-1">
              Tracks forward return trajectories of candidates selected for BUY versus candidates rejected as HOLD across 1, 5, 10, 20, and 60 trading days.
            </p>
          </div>
        </div>

        {/* Recharts Bar Chart */}
        <div className="w-full h-80 pt-2 min-h-[300px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#DCD7CC" strokeOpacity={0.6} />
              <XAxis dataKey="horizon" stroke="#7C8698" fontSize={11} />
              <YAxis stroke="#7C8698" fontSize={11} tickFormatter={(v) => `${v}%`} />
              <Tooltip
                formatter={(value: unknown) => [`${Number(value).toFixed(2)}%`, '']}
                contentStyle={{ backgroundColor: '#FFFFFF', borderColor: '#DCD7CC', color: '#151B26', fontSize: '11px', borderRadius: '3px' }}
              />
              <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }} />
              <Bar dataKey="LLM Simons (BUY)" fill="#1E4E8C" radius={[2, 2, 0, 0]} />
              <Bar dataKey="LLM Simons (HOLD)" fill="#7C8698" radius={[2, 2, 0, 0]} />
              <Bar dataKey="Rules Simons (BUY)" fill="#8A7441" radius={[2, 2, 0, 0]} />
              <Bar dataKey="Nifty 500 Index" fill="#A0A6B2" radius={[2, 2, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Tabular Horizon Breakdown */}
        <div className="overflow-x-auto pt-2">
          <table className="w-full text-left text-xs font-mono text-[#151B26]">
            <thead className="bg-[#F6F4EF] text-[11px] text-[#475060] border-b border-[#DCD7CC]">
              <tr>
                <th className="py-2.5 px-3 font-medium">Horizon</th>
                <th className="py-2.5 px-3 text-right font-medium">LLM Simons BUY</th>
                <th className="py-2.5 px-3 text-right font-medium">LLM Simons HOLD</th>
                <th className="py-2.5 px-3 text-right font-medium">Selection alpha (BUY - HOLD)</th>
                <th className="py-2.5 px-3 text-right font-medium">Rules Simons BUY</th>
                <th className="py-2.5 px-3 text-right font-medium">Nifty 500 return</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E7E3D9]">
              {data.horizonReturns.map((hr) => (
                <tr key={hr.horizonDays} className="hover:bg-[#F6F4EF] transition-colors">
                  <td className="py-2.5 px-3 font-semibold">{hr.horizonDays} Trading Days</td>
                  <td className="py-2.5 px-3 text-right text-[#1E4E8C] font-semibold">{formatPct(hr.llmSimonsBuyAvgPct)}</td>
                  <td className="py-2.5 px-3 text-right text-[#475060]">{formatPct(hr.llmSimonsHoldAvgPct)}</td>
                  <td className="py-2.5 px-3 text-right text-[#1E6548] font-semibold">+{hr.selectionAlphaPct.toFixed(2)}%</td>
                  <td className="py-2.5 px-3 text-right text-[#151B26]">{formatPct(hr.rulesSimonsBuyAvgPct)}</td>
                  <td className="py-2.5 px-3 text-right text-[#7C8698]">{formatPct(hr.nifty500AvgPct)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
