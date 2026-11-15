import { useState, memo } from 'react';
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
import { STRATEGY_THEME } from '../theme/tokens';
import { cn } from '../utils/cn';

interface EquityCurveProps {
  data: NavHistoryPoint[];
  title?: string;
  isBacktest?: boolean;
}

function EquityCurveComponent({
  data,
  title = 'Equity Trajectories',
}: EquityCurveProps) {
  const [activeCohort, setActiveCohort] = useState<'ALL' | 'LLM' | 'RULES'>('ALL');
  const [hoveredSeries, setHoveredSeries] = useState<string | null>(null);

  const seriesMap: Record<string, string> = {
    simons: 'simons',
    baselineSimons: 'baseline-simons-rules',
    lynch: 'lynch',
    baselineLynch: 'baseline-lynch-rules',
    marks: 'marks',
    baselineMarks: 'baseline-marks-rules',
    jhunjhunwala: 'jhunjhunwala',
    baselineRj: 'baseline-rj-rules',
    stockmindsCore: 'stockminds-core',
    baselineVarsity: 'baseline-varsity-rules',
    nifty500: 'nifty500',
  };

  const isSeriesVisible = (key: string) => {
    if (key === 'nifty500') return true;
    const isControl = key.startsWith('baseline');
    if (activeCohort === 'LLM') return !isControl;
    if (activeCohort === 'RULES') return isControl;
    return true;
  };

  return (
    <div className="border border-border-hairline bg-surface-inset rounded-lg p-5 sm:p-6 space-y-4 font-sans">
      
      {/* 1. Header with Title & Compact Cohort Selector */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 border-b border-border-hairline pb-3.5">
        <div className="flex items-center gap-3">
          <h3 className="text-base sm:text-lg font-display font-medium text-white">
            {title}
          </h3>
        </div>

        {/* Segmented Cohort Switcher */}
        <div
          role="tablist"
          aria-label="Filter strategy cohorts"
          className="flex items-center p-0.5 rounded-md bg-surface-well border border-border-hairline text-xs font-mono flex-shrink-0"
        >
          {(['ALL', 'LLM', 'RULES'] as const).map((cohort) => (
            <button
              key={cohort}
              role="tab"
              aria-selected={activeCohort === cohort}
              onClick={() => setActiveCohort(cohort)}
              className={cn(
                "px-3 py-1.5 rounded transition-colors cursor-pointer text-xs font-mono",
                activeCohort === cohort
                  ? "bg-brand-blue-soft text-brand-blue-text font-semibold border border-brand-blue/40"
                  : "text-zinc-400 hover:text-white border border-transparent"
              )}
            >
              {cohort === 'ALL' ? 'All (11)' : cohort === 'LLM' ? 'LLMs (5)' : 'Rules (5)'}
            </button>
          ))}
        </div>
      </div>

      {/* 2. High-Legibility Line Chart */}
      <div className="w-full h-80 sm:h-96 min-h-[340px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 10, right: 15, left: 5, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
            <XAxis
              dataKey="date"
              stroke="#71717A"
              fontSize={12}
              tickMargin={10}
              fontFamily="JetBrains Mono"
              tickLine={false}
            />
            <YAxis
              stroke="#71717A"
              fontSize={12}
              domain={['dataMin - 1000', 'dataMax + 1000']}
              tickFormatter={(v) => formatPaiseCompact(v * 100)}
              fontFamily="JetBrains Mono"
              tickLine={false}
              axisLine={false}
            />
            <Tooltip
              content={({ active, payload, label }) => {
                if (active && payload && payload.length) {
                  return (
                    <div className="p-3.5 shadow-2xl text-xs sm:text-sm space-y-2 bg-[#161616] border border-border-hairline rounded font-mono">
                      <p className="font-semibold text-white border-b pb-1.5 border-border-hairline">
                        Date: {label}
                      </p>
                      <div className="space-y-1.5 max-h-56 overflow-y-auto pr-1">
                        {payload.map((item) => {
                          const themeKey = seriesMap[item.dataKey as string] || 'nifty500';
                          const config = STRATEGY_THEME[themeKey] || STRATEGY_THEME.nifty500;
                          return (
                            <div
                              key={item.dataKey as string}
                              className="flex justify-between items-center gap-5 text-xs"
                            >
                              <span className="flex items-center gap-2" style={{ color: config.color }}>
                                <span
                                  className="w-2 h-2 rounded-full flex-shrink-0"
                                  style={{ backgroundColor: config.color }}
                                />
                                <span>{config.shortName}:</span>
                              </span>
                              <span className="font-bold text-white tabular-nums">
                                {formatPaiseToRupees(Number(item.value) * 100)}
                              </span>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  );
                }
                return null;
              }}
            />
            <Legend
              wrapperStyle={{ fontSize: '11px', paddingTop: '14px', fontFamily: 'JetBrains Mono' }}
              onMouseEnter={(o) => setHoveredSeries(o.dataKey as string)}
              onMouseLeave={() => setHoveredSeries(null)}
            />

            {Object.entries(seriesMap).map(([pointKey, themeKey]) => {
              const config = STRATEGY_THEME[themeKey] || STRATEGY_THEME.nifty500;
              if (!isSeriesVisible(pointKey)) return null;

              const isHovered = hoveredSeries === pointKey;
              const opacity = hoveredSeries ? (isHovered ? 1.0 : 0.15) : 0.85;
              const strokeWidth = isHovered ? 3 : pointKey === 'nifty500' ? 1.5 : 2;

              return (
                <Line
                  key={pointKey}
                  type="monotone"
                  dataKey={pointKey}
                  name={config.shortName}
                  stroke={config.color}
                  strokeWidth={strokeWidth}
                  strokeOpacity={opacity}
                  strokeDasharray={config.strokeDasharray}
                  dot={false}
                  activeDot={{ r: 4 }}
                />
              );
            })}
          </LineChart>
        </ResponsiveContainer>
      </div>

    </div>
  );
}

export default memo(EquityCurveComponent);
