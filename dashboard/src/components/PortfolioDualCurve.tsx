import { useState } from 'react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from 'recharts';
import { formatPaiseToRupees, formatPct } from '../utils/formatters';
import { cn } from '../utils/cn';

interface NavDataPoint {
  date: string;
  portfolioValuePaise: number;
  investedCapitalPaise: number;
}

interface PortfolioDualCurveProps {
  navPoints: NavDataPoint[];
  color?: string;
  height?: number;
}

export default function PortfolioDualCurve({
  navPoints,
  color = '#10B981',
  height = 240,
}: PortfolioDualCurveProps) {
  const [timeRange, setTimeRange] = useState<'1W' | '1M' | '3M' | 'ALL'>('ALL');

  // Ensure at least 2 points for smooth curve rendering even on single-session runs
  const effectivePoints = (() => {
    if (!navPoints || navPoints.length === 0) return [];
    if (navPoints.length >= 2) return navPoints;

    const current = navPoints[0];
    const initialPaise = current.investedCapitalPaise || 50000000;

    const d = new Date(current.date || new Date().toISOString().split('T')[0]);
    d.setDate(d.getDate() - 1);
    const prevDate = d.toISOString().split('T')[0];
    return [
      {
        date: prevDate,
        portfolioValuePaise: initialPaise,
        investedCapitalPaise: initialPaise,
      },
      current,
    ];
  })();

  // Filter data points based on time range
  const filteredData = (() => {
    if (effectivePoints.length === 0) return [];
    if (timeRange === 'ALL' || effectivePoints.length <= 5) return effectivePoints;
    const count = timeRange === '1W' ? 5 : timeRange === '1M' ? 12 : 25;
    return effectivePoints.slice(-Math.min(count, effectivePoints.length));
  })();

  // Chart domain bounds
  const values = filteredData.flatMap((d) => [
    d.portfolioValuePaise / 100,
    d.investedCapitalPaise / 100,
  ]);
  const rawMin = values.length > 0 ? Math.min(...values) : 500000;
  const rawMax = values.length > 0 ? Math.max(...values) : 505000;
  const spread = rawMax - rawMin;
  const pad = spread < 200 ? 500 : spread * 0.15;
  const minVal = Math.floor(rawMin - pad);
  const maxVal = Math.ceil(rawMax + pad);

  return (
    <div className="space-y-3 font-sans">
      {/* Chart Sub-Header with Dual Legend & Timeframe Selector */}
      <div className="flex flex-wrap items-center justify-between gap-3 text-xs font-mono">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-0.5 rounded-full" style={{ backgroundColor: color }} />
            <span className="text-zinc-300">Portfolio Value</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-0.5 border-b border-dashed border-zinc-500" />
            <span className="text-zinc-500">Invested Capital</span>
          </div>
        </div>

        {/* Timeframe Range Selector (1W, 1M, 3M, ALL) */}
        <div className="flex items-center gap-1 p-0.5 rounded bg-[#121212] border border-border-hairline text-[11px]">
          {(['1W', '1M', '3M', 'ALL'] as const).map((r) => (
            <button
              key={r}
              onClick={() => setTimeRange(r)}
              className={cn(
                "px-2 py-0.5 rounded transition-colors cursor-pointer",
                timeRange === r
                  ? "bg-white/15 text-white font-semibold"
                  : "text-zinc-500 hover:text-zinc-300"
              )}
            >
              {r}
            </button>
          ))}
        </div>
      </div>

      {/* Main Interactive Dual Chart */}
      <div style={{ width: '100%', height }} className="relative">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={filteredData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="valueFillGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={color} stopOpacity={0.25} />
                <stop offset="95%" stopColor={color} stopOpacity={0.0} />
              </linearGradient>
            </defs>

            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />

            <XAxis
              dataKey="date"
              stroke="#52525b"
              fontSize={10}
              tickMargin={6}
              fontFamily="JetBrains Mono"
            />
            <YAxis
              domain={[minVal, maxVal]}
              stroke="#52525b"
              fontSize={10}
              tickFormatter={(v) => `₹${(v / 1000).toFixed(1)}k`}
              orientation="right"
              fontFamily="JetBrains Mono"
              width={56}
            />

            <Tooltip
              content={({ active, payload, label }) => {
                if (active && payload && payload.length) {
                  const data = payload[0].payload as NavDataPoint;
                  const deltaPaise = data.portfolioValuePaise - data.investedCapitalPaise;
                  const deltaPct =
                    data.investedCapitalPaise > 0
                      ? (deltaPaise / data.investedCapitalPaise) * 100
                      : 0;

                  return (
                    <div className="p-3 bg-[#161616] border border-border-hairline shadow-2xl rounded font-mono text-xs space-y-1.5 z-50">
                      <div className="text-[10px] text-zinc-400 border-b border-border-hairline pb-1 font-sans">
                        Session: {label}
                      </div>
                      <div className="flex justify-between gap-4">
                        <span className="text-zinc-400">Current NAV:</span>
                        <span className="font-semibold text-white">
                          {formatPaiseToRupees(data.portfolioValuePaise)}
                        </span>
                      </div>
                      <div className="flex justify-between gap-4">
                        <span className="text-zinc-500">Invested:</span>
                        <span className="text-zinc-300">
                          {formatPaiseToRupees(data.investedCapitalPaise)}
                        </span>
                      </div>
                      <div className="flex justify-between gap-4 pt-1 border-t border-border-hairline">
                        <span className="text-zinc-400">P&L Spread:</span>
                        <span
                          className={cn(
                            "font-bold",
                            deltaPaise > 0
                              ? "text-positive"
                              : deltaPaise < 0
                              ? "text-negative"
                              : "text-zinc-400"
                          )}
                        >
                          {deltaPaise > 0 ? `+${formatPaiseToRupees(deltaPaise)}` : formatPaiseToRupees(deltaPaise)} ({formatPct(deltaPct)})
                        </span>
                      </div>
                    </div>
                  );
                }
                return null;
              }}
            />

            {/* Shaded Area Under Portfolio Value Curve */}
            <Area
              type="monotone"
              dataKey={(d) => d.portfolioValuePaise / 100}
              stroke={color}
              strokeWidth={2}
              fill="url(#valueFillGradient)"
              isAnimationActive={true}
            />

            {/* Dashed Baseline Curve for Invested Capital */}
            <Line
              type="monotone"
              dataKey={(d) => d.investedCapitalPaise / 100}
              stroke="#71717a"
              strokeWidth={1.5}
              strokeDasharray="4 4"
              dot={false}
              isAnimationActive={true}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
