import { useState } from 'react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
} from 'recharts';
import type { NavHistoryPoint } from '../types';
import { formatPaiseCompact, formatPaiseToRupees } from '../utils/formatters';

interface EquityCurveProps {
  data: NavHistoryPoint[];
  title?: string;
  isBacktest?: boolean;
}

const AGENT_COLORS: Record<string, { label: string; color: string; strokeDasharray?: string }> = {
  simons: { label: 'Simons (LLM)', color: '#2563eb' }, // Blue
  lynch: { label: 'Peter Lynch', color: '#059669' }, // Green
  marks: { label: 'Howard Marks', color: '#d97706' }, // Amber
  jhunjhunwala: { label: 'Jhunjhunwala', color: '#7c3aed' }, // Purple
  stockmindsCore: { label: 'Varsity Core', color: '#0891b2' }, // Cyan
  baselineSimons: { label: 'Baseline (Rules)', color: '#dc2626', strokeDasharray: '4 4' }, // Dashed Red
  nifty500: { label: 'Nifty 500 Index', color: '#64748b', strokeDasharray: '2 2' }, // Dashed Slate
};

export default function EquityCurve({ data, title = 'Multi-Agent Portfolio Equity Curves', isBacktest = false }: EquityCurveProps) {
  const [activeSeries, setActiveSeries] = useState<Record<string, boolean>>({
    simons: true,
    lynch: true,
    marks: true,
    jhunjhunwala: true,
    stockmindsCore: true,
    baselineSimons: true,
    nifty500: true,
  });

  const toggleSeries = (key: string) => {
    setActiveSeries((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  return (
    <div className="bg-white dark:bg-stone-900 rounded-xl border border-stone-200 dark:border-stone-800 p-5 shadow-sm">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 mb-4">
        <div>
          <h3 className="text-lg font-semibold text-stone-900 dark:text-stone-100 flex items-center gap-2">
            {title}
            {isBacktest && (
              <span className="text-xs px-2 py-0.5 rounded bg-purple-100 text-purple-800 dark:bg-purple-950/60 dark:text-purple-300 font-mono">
                BACKTEST_DERIVED
              </span>
            )}
          </h3>
          <p className="text-xs text-stone-500 dark:text-stone-400">
            Portfolio Net Asset Value (NAV) starting at ₹1,00,000.00 base.
          </p>
        </div>

        {/* Series Filter Toggles */}
        <div className="flex flex-wrap gap-1.5 text-xs">
          {Object.entries(AGENT_COLORS).map(([key, config]) => {
            const isEnabled = activeSeries[key];
            return (
              <button
                key={key}
                onClick={() => toggleSeries(key)}
                className={`px-2.5 py-1 rounded-full border transition-all flex items-center gap-1.5 ${
                  isEnabled
                    ? 'border-transparent text-white shadow-xs'
                    : 'bg-stone-100 dark:bg-stone-800 text-stone-400 border-stone-200 dark:border-stone-700 opacity-60'
                }`}
                style={{ backgroundColor: isEnabled ? config.color : undefined }}
              >
                <span className="w-2 h-2 rounded-full bg-white/80" />
                <span>{config.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      <div className="w-full h-80 sm:h-96">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" strokeOpacity={0.6} />
            <XAxis dataKey="date" stroke="#64748b" fontSize={11} tickMargin={8} />
            <YAxis
              stroke="#64748b"
              fontSize={11}
              domain={['dataMin - 1000', 'dataMax + 1000']}
              tickFormatter={(v) => formatPaiseCompact(v * 100)}
            />
            <Tooltip
              content={({ active, payload, label }) => {
                if (active && payload && payload.length) {
                  return (
                    <div className="bg-white dark:bg-stone-900 border border-stone-200 dark:border-stone-700 p-3 rounded-lg shadow-lg text-xs space-y-1">
                      <p className="font-semibold text-stone-900 dark:text-stone-100 border-b pb-1 mb-1 border-stone-200 dark:border-stone-800">
                        Date: {label}
                      </p>
                      {payload.map((item) => (
                        <div key={item.dataKey as string} className="flex justify-between items-center gap-4">
                          <span className="flex items-center gap-1.5" style={{ color: item.color }}>
                            <span className="w-2 h-2 rounded-full" style={{ backgroundColor: item.color }} />
                            <span>{AGENT_COLORS[item.dataKey as string]?.label || String(item.dataKey)}:</span>
                          </span>
                          <span className="font-mono font-medium text-stone-900 dark:text-stone-100">
                            {formatPaiseToRupees(Number(item.value) * 100)}
                          </span>
                        </div>
                      ))}
                    </div>
                  );
                }
                return null;
              }}
            />
            <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }} />

            {Object.entries(AGENT_COLORS).map(([key, config]) =>
              activeSeries[key] ? (
                <Line
                  key={key}
                  type="monotone"
                  dataKey={key}
                  name={config.label}
                  stroke={config.color}
                  strokeWidth={key === 'simons' || key === 'baselineSimons' ? 2.5 : 2}
                  strokeDasharray={config.strokeDasharray}
                  dot={{ r: 3 }}
                  activeDot={{ r: 6 }}
                />
              ) : null
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
