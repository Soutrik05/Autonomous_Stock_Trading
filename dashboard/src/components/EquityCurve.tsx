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

interface EquityCurveProps {
  data: NavHistoryPoint[];
  title?: string;
  isBacktest?: boolean;
}

function EquityCurveComponent({
  data,
  title = 'Multi-Agent Portfolio Equity Curves',
  isBacktest = false,
}: EquityCurveProps) {
  // Active series visibility
  const [activeSeries, setActiveSeries] = useState<Record<string, boolean>>({
    simons: true,
    lynch: true,
    marks: true,
    jhunjhunwala: true,
    stockmindsCore: true,
    baselineSimons: true,
    nifty500: true,
  });

  // Focused series on hover (Intelligent Focus & Dimming UX)
  const [hoveredSeries, setHoveredSeries] = useState<string | null>(null);

  const toggleSeries = (key: string) => {
    setActiveSeries((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  // Map NavHistoryPoint keys to StrategyTheme keys
  const seriesMap: Record<string, string> = {
    simons: 'simons',
    lynch: 'lynch',
    marks: 'marks',
    jhunjhunwala: 'jhunjhunwala',
    stockmindsCore: 'stockminds-core',
    baselineSimons: 'baseline-simons-rules',
    nifty500: 'nifty500',
  };

  return (
    <div className="arena-glass p-6 sm:p-7 space-y-5">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h3 className="text-base sm:text-lg font-bold text-white flex items-center gap-2">
            <span>{title}</span>
            {isBacktest && (
              <span className="text-[10px] px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 font-mono font-medium border border-purple-500/30">
                Backtest Simulation
              </span>
            )}
          </h3>
          <p className="text-xs text-slate-400">
            Net asset value indexed to ₹1,00,000.00 base. Hover any curve or chip to focus.
          </p>
        </div>

        {/* Series Filter Chips with Hover Focus */}
        <div className="flex flex-wrap gap-1.5 text-xs font-mono">
          {Object.entries(seriesMap).map(([pointKey, themeKey]) => {
            const config = STRATEGY_THEME[themeKey] || STRATEGY_THEME.nifty500;
            const isEnabled = activeSeries[pointKey];
            const isHovered = hoveredSeries === pointKey;

            return (
              <button
                key={pointKey}
                onClick={() => toggleSeries(pointKey)}
                onMouseEnter={() => setHoveredSeries(pointKey)}
                onMouseLeave={() => setHoveredSeries(null)}
                className={`px-2.5 py-1 rounded-md border transition-all cursor-pointer flex items-center gap-1.5 ${
                  isEnabled
                    ? isHovered
                      ? 'ring-1 ring-cyan-400 font-semibold text-white'
                      : 'border-transparent text-white'
                    : 'bg-white/5 text-slate-500 border-white/10 opacity-50'
                }`}
                style={{
                  backgroundColor: isEnabled ? config.color : undefined,
                }}
              >
                <span className="w-1.5 h-1.5 rounded-full bg-white/90" />
                <span>{config.shortName}</span>
              </button>
            );
          })}
        </div>
      </div>

      <div className="w-full h-80 sm:h-96 min-h-[320px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
            <XAxis dataKey="date" stroke="#64748B" fontSize={11} tickMargin={8} />
            <YAxis
              stroke="#64748B"
              fontSize={11}
              domain={['dataMin - 1000', 'dataMax + 1000']}
              tickFormatter={(v) => formatPaiseCompact(v * 100)}
            />
            <Tooltip
              content={({ active, payload, label }) => {
                if (active && payload && payload.length) {
                  return (
                    <div className="arena-glass p-3.5 shadow-2xl text-xs space-y-1.5 bg-[#0B0F19]/95 border border-white/15 backdrop-blur-xl">
                      <p className="font-bold text-white border-b pb-1 mb-1 border-white/10 font-sans">
                        Trading Date: {label}
                      </p>
                      {payload.map((item) => {
                        const themeKey = seriesMap[item.dataKey as string] || 'nifty500';
                        const config = STRATEGY_THEME[themeKey] || STRATEGY_THEME.nifty500;
                        return (
                          <div
                            key={item.dataKey as string}
                            className="flex justify-between items-center gap-4 font-mono text-[11px]"
                          >
                            <span className="flex items-center gap-1.5" style={{ color: config.color }}>
                              <span
                                className="w-2 h-2 rounded-full"
                                style={{ backgroundColor: config.color }}
                              />
                              <span>{config.shortName}:</span>
                            </span>
                            <span className="font-semibold text-white">
                              {formatPaiseToRupees(Number(item.value) * 100)}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  );
                }
                return null;
              }}
            />
            <Legend
              wrapperStyle={{ fontSize: '11px', paddingTop: '12px' }}
              onMouseEnter={(o) => setHoveredSeries(o.dataKey as string)}
              onMouseLeave={() => setHoveredSeries(null)}
            />

            {Object.entries(seriesMap).map(([pointKey, themeKey]) => {
              const config = STRATEGY_THEME[themeKey] || STRATEGY_THEME.nifty500;
              if (!activeSeries[pointKey]) return null;

              // Intelligent Focus & Dimming UX
              const isHovered = hoveredSeries === pointKey;
              const opacity = hoveredSeries ? (isHovered ? 1.0 : 0.15) : 0.85;
              const strokeWidth = isHovered ? 3.5 : pointKey === 'simons' || pointKey === 'baselineSimons' ? 2.5 : 2;

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
                  dot={{ r: isHovered ? 4 : 2, fill: config.color }}
                  activeDot={{ r: 5 }}
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
