import { useState } from 'react';
import {
  ResponsiveContainer,
  LineChart,
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
  color = '#818CF8', // Modern Indigo from reference design
  height = 240,
}: PortfolioDualCurveProps) {
  const [timeRange, setTimeRange] = useState<'1W' | '1M' | '6M' | '1Y' | 'ALL'>('ALL');

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
    const count = timeRange === '1W' ? 5 : timeRange === '1M' ? 12 : timeRange === '6M' ? 30 : 60;
    return effectivePoints.slice(-Math.min(count, effectivePoints.length));
  })();

  // Chart domain bounds: Padded Y-axis so small moves don't clip or look flat
  const values = filteredData.flatMap((d) => [
    d.portfolioValuePaise / 100,
    d.investedCapitalPaise / 100,
  ]);
  const rawMin = values.length > 0 ? Math.min(...values) : 500000;
  const rawMax = values.length > 0 ? Math.max(...values) : 505000;
  const spread = rawMax - rawMin;
  // Ensure at least ₹15,000 minimum vertical spread so minor daily ticks have natural, graceful amplitude
  const minSpread = Math.max((rawMax || 500000) * 0.03, 15000);
  const effectiveSpread = Math.max(spread, minSpread);
  const pad = effectiveSpread * 0.25;
  const minVal = Math.floor(rawMin - pad);
  const maxVal = Math.ceil(rawMax + pad);

  // Latest snapshot metrics for reference header
  const latestPoint = filteredData.length > 0 ? filteredData[filteredData.length - 1] : null;
  const currentNav = latestPoint ? latestPoint.portfolioValuePaise : 50000000;
  const investedNav = latestPoint ? latestPoint.investedCapitalPaise : 50000000;
  const pnlPaise = currentNav - investedNav;
  const pnlPct = investedNav > 0 ? (pnlPaise / investedNav) * 100 : 0;

  return (
    <div className="space-y-4 font-sans">
      {/* Portfolio Analysis Header Strip (Modeled after Reference Image) */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-2 border-b border-border-hairline">
        {/* Left: Current Valuation with Indigo indicator */}
        <div className="space-y-0.5">
          <div className="flex items-center gap-1.5 text-xs text-zinc-400 font-sans">
            <span className="w-2.5 h-2.5 rounded-sm bg-[#818CF8]" />
            <span>Current NAV</span>
          </div>
          <div className="flex items-baseline gap-2.5">
            <span className="text-xl sm:text-2xl font-bold font-mono text-white tabular-nums">
              {formatPaiseToRupees(currentNav)}
            </span>
            <span
              className={cn(
                "text-xs font-mono font-medium tabular-nums",
                pnlPaise >= 0 ? "text-positive" : "text-negative"
              )}
            >
              {pnlPaise >= 0 ? '+' : ''}{formatPaiseToRupees(pnlPaise)} ({formatPct(pnlPct)})
            </span>
          </div>
        </div>

        {/* Right: Seed Capital & Timeframe Controls */}
        <div className="flex flex-wrap items-center gap-6">
          <div className="text-right space-y-0.5">
            <div className="flex items-center justify-end gap-1.5 text-xs text-zinc-400 font-sans">
              <span className="w-2.5 h-2.5 rounded-sm bg-zinc-500 border border-zinc-400" />
              <span>Initial Seed Capital</span>
            </div>
            <div className="text-base sm:text-lg font-medium font-mono text-zinc-300 tabular-nums">
              {formatPaiseToRupees(investedNav)}
            </div>
          </div>

          {/* Timeframe Range Selector (1W, 1M, 6M, 1Y, ALL) */}
          <div className="flex items-center gap-1 p-0.5 rounded-md bg-[#121212] border border-border-hairline text-xs font-mono">
            {(['1W', '1M', '6M', '1Y', 'ALL'] as const).map((r) => (
              <button
                key={r}
                onClick={() => setTimeRange(r)}
                className={cn(
                  "px-2.5 py-1 rounded transition-colors cursor-pointer text-xs",
                  timeRange === r
                    ? "bg-white/15 text-white font-semibold"
                    : "text-zinc-400 hover:text-white"
                )}
              >
                {r}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Main Pure-Line Chart (No Area Fill Gradient) */}
      <div style={{ width: '100%', height }} className="relative">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={filteredData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
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
              tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}k`}
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
                        <span className="text-zinc-400">Net Return:</span>
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

            {/* Line Only: Modern Indigo Line with Clean Curve */}
            <Line
              type="monotone"
              dataKey={(d) => d.portfolioValuePaise / 100}
              stroke={color}
              strokeWidth={2.5}
              dot={false}
              isAnimationActive={true}
            />

            {/* Dashed Baseline Curve for Invested Capital */}
            <Line
              type="monotone"
              dataKey={(d) => d.investedCapitalPaise / 100}
              stroke="#64748b"
              strokeWidth={1.5}
              strokeDasharray="4 4"
              dot={false}
              isAnimationActive={true}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
