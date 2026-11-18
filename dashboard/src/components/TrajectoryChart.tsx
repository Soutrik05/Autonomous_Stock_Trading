import React from 'react';
import { getAgentDisplayName } from '../constants/personas';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ReferenceDot,
} from 'recharts';
import { TrendingUp } from 'lucide-react';
import { cn } from '../utils/cn';

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
  /** Red Hat Display 600, 21px heading above the chart (Home top section). */
  title?: string;
  /** 14px grey subtitle under the title (Home top section). */
  subtitle?: string;
}

const COMPOSITE_COLORS = {
  llm: '#10b981',
  rules: '#d9d2c1',
  nifty: '#4F8FE0',
};

function RightNowBox({ color, name, value }: { color: string; name: string; value: number | null }) {
  const missing = value === null || Number.isNaN(value);
  return (
    <div className="flex items-center gap-2 px-2.5 py-2 rounded border border-border-hairline bg-white/[0.02] min-w-0">
      <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />
      <span className="text-[11px] text-zinc-400 font-mono truncate">{name}</span>
      <span
        className={cn(
          'ml-auto text-[12px] font-mono font-semibold tabular-nums',
          missing ? 'text-zinc-500' : value! >= 0 ? 'text-positive' : 'text-negative'
        )}
      >
        {missing ? '—' : `${value! >= 0 ? '+' : ''}${value!.toFixed(2)}%`}
      </span>
    </div>
  );
}

export const TrajectoryChart: React.FC<TrajectoryChartProps> = React.memo(({
  data,
  mode,
  onModeChange,
  title,
  subtitle,
}) => {
  const last = data.length > 0 ? data[data.length - 1] : null;

  return (
    <div className="p-5 sm:p-6 space-y-3 font-mono text-xs">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border-hairline pb-3">
        <div className="min-w-0">
          {title ? (
            <>
              <h2
                className="font-sans text-white"
                style={{ fontFamily: "var(--font-headline), 'Red Hat Display Fallback', system-ui, sans-serif", fontWeight: 600, fontSize: '21px' }}
              >
                {title}
              </h2>
              {subtitle && (
                <p className="text-[14px] text-zinc-400 font-sans mt-1">{subtitle}</p>
              )}
            </>
          ) : (
            <div className="flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-emerald-400" />
              <h2 className="font-sans text-sm font-medium text-zinc-200">
                Observed Return Trajectory
              </h2>
            </div>
          )}
        </div>

        {/* Segmented View Switcher */}
        <div className="flex items-center p-0.5 rounded bg-[#1C1C1C] border border-white/10 text-[10px] flex-shrink-0">
          <button
            onClick={() => onModeChange('COMPOSITE')}
            className={`px-2 py-0.5 rounded transition-colors cursor-pointer ${
              mode === 'COMPOSITE'
                ? 'bg-white/[0.12] text-white font-medium'
                : 'text-zinc-400 hover:text-white'
            }`}
          >
            Average
          </button>
          <button
            onClick={() => onModeChange('PERSONAS')}
            className={`px-2 py-0.5 rounded transition-colors cursor-pointer ${
              mode === 'PERSONAS'
                ? 'bg-white/[0.12] text-white font-medium'
                : 'text-zinc-400 hover:text-white'
            }`}
          >
            Each agent
          </button>
        </div>
      </div>

      {/* Recharts Plot */}
      <div className="h-[260px] w-full pt-1">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 10, right: 72, left: 8, bottom: 0 }}>
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
                  name="AI agents"
                  stroke={COMPOSITE_COLORS.llm}
                  strokeWidth={3}
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="rulesComposite"
                  name="Rules twins"
                  stroke={COMPOSITE_COLORS.rules}
                  strokeWidth={2}
                  strokeDasharray="7 5"
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="nifty500"
                  name="Nifty 500"
                  stroke={COMPOSITE_COLORS.nifty}
                  strokeWidth={2}
                  strokeDasharray="1 5"
                  strokeLinecap="round"
                  dot={false}
                />

                {last && (() => {
                  // Nudge the three end labels apart by their final relative order so they
                  // never sit on top of one another.
                  const rows: Array<{ key: 'llmComposite' | 'rulesComposite' | 'nifty500'; color: string; label: string }> = [
                    { key: 'llmComposite', color: COMPOSITE_COLORS.llm, label: 'AI agents' },
                    { key: 'rulesComposite', color: COMPOSITE_COLORS.rules, label: 'Rules twins' },
                    { key: 'nifty500', color: COMPOSITE_COLORS.nifty, label: 'Nifty 500' },
                  ];
                  const sorted = [...rows].sort((a, b) => last[a.key] - last[b.key]);
                  return sorted.map((row, i) => {
                    return (
                      <ReferenceDot
                        key={row.key}
                        x={last.date}
                        y={last[row.key]}
                        r={3}
                        fill={row.color}
                        stroke="none"
                        label={{
                          value: row.label,
                          position: 'right',
                          fill: row.color,
                          fontSize: 10,
                          fontFamily: 'JetBrains Mono',
                          dy: (i - 1) * 11,
                        }}
                      />
                    );
                  });
                })()}
              </>
            ) : (
              <>
                <Line
                  type="monotone"
                  dataKey="simons"
                  name={getAgentDisplayName('simons')}
                  stroke="#10B981"
                  strokeWidth={2}
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="marks"
                  name={getAgentDisplayName('marks')}
                  stroke="#38BDF8"
                  strokeWidth={1.5}
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="lynch"
                  name={getAgentDisplayName('lynch')}
                  stroke="#E0E0E0"
                  strokeWidth={1.5}
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="nifty500"
                  name="Nifty 500 Index"
                  stroke="#64748B"
                  strokeWidth={1.5}
                  strokeDasharray="2 2"
                  dot={false}
                />
              </>
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* "Right now" boxes: one per composite line, latest real value */}
      {mode === 'COMPOSITE' && (
        <div className="grid grid-cols-3 gap-2 pt-1">
          <RightNowBox color={COMPOSITE_COLORS.llm} name="AI agents" value={last ? last.llmComposite : null} />
          <RightNowBox color={COMPOSITE_COLORS.rules} name="Rules twins" value={last ? last.rulesComposite : null} />
          <RightNowBox color={COMPOSITE_COLORS.nifty} name="Nifty 500" value={last ? last.nifty500 : null} />
        </div>
      )}

      {/* Chart Legend */}
      <div className="pt-2 border-t border-border-subtle flex flex-wrap items-center justify-between gap-2 text-[11px] text-zinc-400">
        <div className="flex items-center gap-3">
          {mode === 'COMPOSITE' ? (
            <>
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-0.5 inline-block" style={{ backgroundColor: COMPOSITE_COLORS.llm }} />
                <span className="text-zinc-300">AI agents</span>
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-0.5 inline-block border-b border-dashed" style={{ borderColor: COMPOSITE_COLORS.rules }} />
                <span className="text-zinc-400">Rules twins</span>
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-0.5 inline-block border-b border-dotted" style={{ borderColor: COMPOSITE_COLORS.nifty }} />
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
                <span className="w-2.5 h-0.5 bg-slate-500 inline-block border-b border-dotted border-slate-500" />
                <span className="text-zinc-400">Nifty 500</span>
              </span>
            </>
          )}
        </div>
        {data.length > 0 && (
          <div className="text-[10px] font-mono text-zinc-500">
            {data[0]?.fullDate || data[0]?.date} → {data[data.length - 1]?.fullDate || data[data.length - 1]?.date}
          </div>
        )}
      </div>
    </div>
  );
});

TrajectoryChart.displayName = 'TrajectoryChart';
