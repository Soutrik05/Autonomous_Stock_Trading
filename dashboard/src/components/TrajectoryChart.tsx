import React from 'react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from 'recharts';
import { TrendingUp } from 'lucide-react';

export interface TrajectoryChartPoint {
  date: string;
  fullDate: string;
  llmComposite: number;
  rulesComposite: number;
  nifty500: number;
  simons: number;
  marks: number;
  lynch: number;
}

interface TrajectoryChartProps {
  data: TrajectoryChartPoint[];
  mode: 'COMPOSITE' | 'PERSONAS';
  onModeChange: (mode: 'COMPOSITE' | 'PERSONAS') => void;
}

export const TrajectoryChart: React.FC<TrajectoryChartProps> = React.memo(({
  data,
  mode,
  onModeChange,
}) => {
  return (
    <div className="p-5 sm:p-6 space-y-3 font-mono text-xs">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border-hairline pb-3">
        <div className="flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-emerald-400" />
          <h2 className="font-sans text-xs sm:text-sm font-semibold uppercase tracking-wider text-white">
            Observed Cumulative Return Trajectories
          </h2>
        </div>

        {/* Segmented View Switcher */}
        <div className="flex items-center p-0.5 rounded bg-[#1C1C1C] border border-white/10 text-[10px]">
          <button
            onClick={() => onModeChange('COMPOSITE')}
            className={`px-2 py-0.5 rounded transition-colors cursor-pointer ${
              mode === 'COMPOSITE'
                ? 'bg-white/[0.12] text-white font-medium'
                : 'text-zinc-400 hover:text-white'
            }`}
          >
            Composite (LLM vs Rules)
          </button>
          <button
            onClick={() => onModeChange('PERSONAS')}
            className={`px-2 py-0.5 rounded transition-colors cursor-pointer ${
              mode === 'PERSONAS'
                ? 'bg-white/[0.12] text-white font-medium'
                : 'text-zinc-400 hover:text-white'
            }`}
          >
            Key Personas
          </button>
        </div>
      </div>

      {/* Recharts Plot */}
      <div className="h-[230px] w-full pt-1">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 10, right: 16, left: 8, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255, 255, 255, 0.05)" />
            <XAxis
              dataKey="date"
              stroke="#757575"
              fontSize={10}
              tickLine={false}
              axisLine={{ stroke: 'rgba(255, 255, 255, 0.08)' }}
              fontFamily="JetBrains Mono"
            />
            <YAxis
              stroke="#757575"
              fontSize={10}
              width={56}
              tickFormatter={(v) => `${Number(v) > 0 ? '+' : ''}${Number(v).toFixed(2)}%`}
              tickLine={false}
              axisLine={{ stroke: 'rgba(255, 255, 255, 0.08)' }}
              fontFamily="JetBrains Mono"
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#1E1E1E',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                borderRadius: '4px',
                fontSize: '11px',
                fontFamily: 'JetBrains Mono',
              }}
              formatter={(val: any) => [`${Number(val) > 0 ? '+' : ''}${Number(val).toFixed(2)}%`, '']}
            />

            {mode === 'COMPOSITE' ? (
              <>
                <Line
                  type="monotone"
                  dataKey="llmComposite"
                  name="LLM Composite (5 Personas)"
                  stroke="#10B981"
                  strokeWidth={2}
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="rulesComposite"
                  name="Rules Control Composite"
                  stroke="#94A3B8"
                  strokeWidth={1.5}
                  strokeDasharray="4 4"
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="nifty500"
                  name="Nifty 500 Index"
                  stroke="#D4AF37"
                  strokeWidth={1.5}
                  dot={false}
                />
              </>
            ) : (
              <>
                <Line
                  type="monotone"
                  dataKey="simons"
                  name="Jim Simons (LLM)"
                  stroke="#10B981"
                  strokeWidth={2}
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="marks"
                  name="Howard Marks (LLM)"
                  stroke="#38BDF8"
                  strokeWidth={1.5}
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="lynch"
                  name="Peter Lynch (LLM)"
                  stroke="#E0E0E0"
                  strokeWidth={1.5}
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="nifty500"
                  name="Nifty 500 Index"
                  stroke="#D4AF37"
                  strokeWidth={1.5}
                  strokeDasharray="3 3"
                  dot={false}
                />
              </>
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Chart Legend */}
      <div className="pt-2 border-t border-border-subtle flex items-center justify-between text-[11px] text-zinc-400">
        <div className="flex items-center gap-3">
          {mode === 'COMPOSITE' ? (
            <>
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-0.5 bg-positive inline-block" />
                <span className="text-zinc-300">LLM Avg</span>
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-0.5 bg-slate-400 inline-block border-b border-dashed border-slate-400" />
                <span className="text-zinc-400">Rules Avg</span>
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-0.5 bg-accent inline-block" />
                <span className="text-zinc-400">Nifty 500</span>
              </span>
            </>
          ) : (
            <>
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-0.5 bg-positive inline-block" />
                <span className="text-zinc-300">Simons</span>
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-0.5 bg-sky-400 inline-block" />
                <span className="text-zinc-400">Marks</span>
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-0.5 bg-accent inline-block" />
                <span className="text-zinc-400">Nifty 500</span>
              </span>
            </>
          )}
        </div>
      </div>
    </div>
  );
});

TrajectoryChart.displayName = 'TrajectoryChart';

