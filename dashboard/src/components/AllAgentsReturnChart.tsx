import { useEffect, useRef, useState } from 'react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ReferenceLine,
  ReferenceDot,
} from 'recharts';
import type { NavHistoryPoint } from '../types';
import { getAgentName } from '../lib/agentNames';
import { formatPct } from '../utils/formatters';
import { useIntroDone } from '../hooks/useIntro';
import { usePrefersReducedMotion } from '../hooks/usePrefersReducedMotion';
import { SkeletonBlock } from './ui/Skeleton';
import { useDelayedVisible } from '../hooks/useDelayedVisible';
import { cn } from '../utils/cn';

const SESSION_KEY = 'stockminds_all_agents_chart_drawn';
const SEED_NAV = 500000;

/** The 5 LLM/Rules pairs this chart draws, each a {llmKey,rulesKey} into NavHistoryPoint plus
 * the real backend agent id (for the shared name map) and the one colour the pair shares.
 * Colours are deliberately never amber or red (those mean caution/loss elsewhere). */
const PAIRS: Array<{
  base: string;
  llmKey: keyof NavHistoryPoint;
  rulesKey: keyof NavHistoryPoint;
  llmId: string;
  rulesId: string;
  color: string;
}> = [
  { base: 'lynch', llmKey: 'lynch', rulesKey: 'baselineLynch', llmId: 'lynch', rulesId: 'baseline-lynch-rules', color: '#10b981' },
  { base: 'varsity', llmKey: 'stockmindsCore', rulesKey: 'baselineVarsity', llmId: 'varsity', rulesId: 'baseline-varsity-rules', color: '#a3e635' },
  { base: 'jhunjhunwala', llmKey: 'jhunjhunwala', rulesKey: 'baselineRj', llmId: 'jhunjhunwala', rulesId: 'baseline-rj-rules', color: '#4F8FE0' },
  { base: 'simons', llmKey: 'simons', rulesKey: 'baselineSimons', llmId: 'simons', rulesId: 'baseline-simons-rules', color: '#a78bfa' },
  { base: 'marks', llmKey: 'marks', rulesKey: 'baselineMarks', llmId: 'marks', rulesId: 'baseline-marks-rules', color: '#e8dfc8' },
];

type FilterMode = 'ALL' | 'LLM' | 'RULES';

interface ChartRow {
  date: string;
  fullDate: string;
  [key: string]: string | number | null;
}

function toReturnPct(nav: number | undefined): number | null {
  if (nav === undefined || nav === null) return null;
  return ((nav - SEED_NAV) / SEED_NAV) * 100;
}

function shortDate(iso: string): string {
  const parts = iso.split('-');
  return parts.length === 3 ? `${parts[1]}/${parts[2]}` : iso;
}

/** Which of a pair's two lines are visible under the current filter. */
function visibleKeysForPair(pair: (typeof PAIRS)[number], filter: FilterMode): Array<{ key: string; id: string; dashed: boolean }> {
  const out: Array<{ key: string; id: string; dashed: boolean }> = [];
  if (filter !== 'RULES') out.push({ key: pair.llmKey as string, id: pair.llmId, dashed: false });
  if (filter !== 'LLM') out.push({ key: pair.rulesKey as string, id: pair.rulesId, dashed: true });
  return out;
}

function CustomTooltip({
  active,
  payload,
  label,
  visibleSeries,
}: {
  active?: boolean;
  payload?: Array<{ dataKey: string; value: number }>;
  label?: string;
  visibleSeries: Array<{ key: string; id: string; color: string }>;
}) {
  if (!active || !payload || !payload.length) return null;

  const rows = visibleSeries
    .map((s) => {
      const entry = payload.find((p) => p.dataKey === s.key);
      return entry && entry.value !== null && entry.value !== undefined
        ? { ...s, value: entry.value as number }
        : null;
    })
    .filter((r): r is { key: string; id: string; color: string; value: number } => r !== null)
    .sort((a, b) => b.value - a.value);

  return (
    <div
      className="bg-[#1E1E1E] border border-white/10 rounded font-mono"
      style={{ fontSize: '12px', padding: '8px 10px', minWidth: '140px' }}
    >
      <div className="text-zinc-300 font-semibold border-b border-white/10 pb-1 mb-1">{label}</div>
      <div className="space-y-0.5">
        {rows.map((r) => (
          <div key={r.key} className="flex items-center justify-between gap-3">
            <span className="flex items-center gap-1.5 text-zinc-300 truncate">
              <span className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ backgroundColor: r.color }} />
              {getAgentName(r.id)}
            </span>
            <span
              className={cn(
                'tabular-nums flex-shrink-0',
                r.value > 0 ? 'text-positive' : r.value < 0 ? 'text-negative' : 'text-zinc-500'
              )}
            >
              {formatPct(r.value)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

interface AllAgentsReturnChartProps {
  navHistory: NavHistoryPoint[];
  loading: boolean;
}

export default function AllAgentsReturnChart({ navHistory, loading }: AllAgentsReturnChartProps) {
  const [filter, setFilter] = useState<FilterMode>('ALL');
  const [hoveredKey, setHoveredKey] = useState<string | null>(null);
  const [pinnedKey, setPinnedKey] = useState<string | null>(null);
  const introDone = useIntroDone();
  const reducedMotion = usePrefersReducedMotion();

  const highlightKey = pinnedKey ?? hoveredKey;

  // First-ever draw-in animation this session: waits for data + introDone + tab-visible,
  // then plays once and marks the session flag. A later refresh (flag already set) or a
  // background polling update never replays it.
  const [eligible] = useState(() => {
    if (reducedMotion) return false;
    try {
      return sessionStorage.getItem(SESSION_KEY) !== 'true';
    } catch {
      return false;
    }
  });
  const [started, setStarted] = useState(false);
  const startedRef = useRef(false);
  const hasData = navHistory.length >= 2;

  useEffect(() => {
    if (!eligible || !hasData) return;
    let cancelled = false;
    function tryStart() {
      if (cancelled || startedRef.current) return;
      if (introDone && document.visibilityState === 'visible') {
        startedRef.current = true;
        try {
          sessionStorage.setItem(SESSION_KEY, 'true');
        } catch {
          /* ignore */
        }
        setStarted(true);
      }
    }
    const id = window.setTimeout(tryStart, 0);
    document.addEventListener('visibilitychange', tryStart);
    return () => {
      cancelled = true;
      window.clearTimeout(id);
      document.removeEventListener('visibilitychange', tryStart);
    };
  }, [eligible, introDone, hasData]);

  const showSkeleton = useDelayedVisible(loading && navHistory.length === 0);

  // Waiting on the one-time draw gate: show the skeleton rather than a half-drawn or empty
  // chart (also covers the "first load" skeleton rule -- a cached/refreshed load is never
  // eligible, so this branch is skipped entirely then).
  const waitingToDraw = eligible && hasData && !started;

  const rows: ChartRow[] = navHistory.map((pt) => {
    const row: ChartRow = { date: shortDate(pt.date), fullDate: pt.date };
    for (const pair of PAIRS) {
      row[pair.llmKey as string] = toReturnPct(pt[pair.llmKey] as number | undefined);
      row[pair.rulesKey as string] = toReturnPct(pt[pair.rulesKey] as number | undefined);
    }
    return row;
  });

  const visibleSeries = PAIRS.flatMap((pair) =>
    visibleKeysForPair(pair, filter).map((v) => ({
      key: v.key,
      id: v.id,
      color: pair.color,
      dashed: v.dashed,
      base: pair.base,
    }))
  );

  const lastRow = rows.length > 0 ? rows[rows.length - 1] : null;

  // Series with actual final numeric values, sorted by final value descending
  const seriesWithValues = lastRow
    ? visibleSeries
        .map((s) => ({
          ...s,
          value: lastRow[s.key] as number | null,
          name: getAgentName(s.id),
        }))
        .filter((s): s is typeof s & { value: number } => s.value !== null)
        .sort((a, b) => b.value - a.value)
    : [];

  // Vertical anti-collision layout for end-of-line labels:
  // Dynamically relaxes y-offsets when multiple lines converge at similar return values.
  const labelDeltas = (() => {
    if (seriesWithValues.length <= 1) return new Map<string, number>();

    const sorted = [...seriesWithValues];
    const minVal = Math.min(...sorted.map((s) => s.value));
    const maxVal = Math.max(...sorted.map((s) => s.value));
    const valRange = Math.max(0.1, maxVal - minVal);

    // Approximate chart interior height for scaling
    const USABLE_HEIGHT = 250;
    const MIN_LABEL_GAP = 13;

    // Approximate SVG Y pixel positions (0 = top/high return, USABLE_HEIGHT = bottom/low return)
    const rawY = sorted.map((s) => ((maxVal - s.value) / valRange) * (USABLE_HEIGHT - 30) + 15);

    // Downward relaxation pass
    const targetY = [...rawY];
    for (let i = 1; i < targetY.length; i++) {
      if (targetY[i] < targetY[i - 1] + MIN_LABEL_GAP) {
        targetY[i] = targetY[i - 1] + MIN_LABEL_GAP;
      }
    }

    // Upward relaxation pass if bottom label overflows
    const maxY = USABLE_HEIGHT - 10;
    if (targetY[targetY.length - 1] > maxY) {
      targetY[targetY.length - 1] = maxY;
      for (let i = targetY.length - 2; i >= 0; i--) {
        if (targetY[i] > targetY[i + 1] - MIN_LABEL_GAP) {
          targetY[i] = targetY[i + 1] - MIN_LABEL_GAP;
        }
      }
    }

    const deltas = new Map<string, number>();
    sorted.forEach((s, i) => {
      deltas.set(s.key, Math.round(targetY[i] - rawY[i]));
    });
    return deltas;
  })();

  const filterButtons: Array<{ key: FilterMode; label: string }> = [
    { key: 'ALL', label: 'All 10' },
    { key: 'LLM', label: 'AI agents' },
    { key: 'RULES', label: 'Rules twins' },
  ];

  return (
    <div className="glow-box rounded-lg">
      <div className="border border-border-hairline bg-surface-inset rounded-lg overflow-hidden p-5 sm:p-6 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-[13px] text-zinc-400 font-mono">
            Solid lines are AI agents. Dashed lines are their rules twins.
          </p>
          <div
            role="tablist"
            aria-label="Filter agents shown"
            className="flex items-center p-0.5 rounded-md bg-surface-well border border-border-hairline text-xs font-mono flex-shrink-0"
          >
            {filterButtons.map((btn) => (
              <button
                key={btn.key}
                role="tab"
                aria-selected={filter === btn.key}
                onClick={() => setFilter(btn.key)}
                className={cn(
                  'px-3 py-1.5 rounded transition-colors cursor-pointer text-xs',
                  filter === btn.key
                    ? 'bg-brand-blue-soft text-brand-blue-text font-semibold border border-brand-blue/40'
                    : 'text-zinc-400 hover:text-white border border-transparent'
                )}
              >
                {btn.label}
              </button>
            ))}
          </div>
        </div>

        {showSkeleton || waitingToDraw ? (
          <SkeletonBlock className="w-full" style={{ height: '320px' }} />
        ) : !hasData ? (
          <div className="h-[220px] flex items-center justify-center text-sm text-zinc-500 font-mono text-center px-6">
            The chart will appear once there are two days of data.
          </div>
        ) : (
          <>
            <div className="h-[320px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={rows} margin={{ top: 10, right: 110, left: 8, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                  <XAxis
                    dataKey="date"
                    stroke="#757575"
                    fontSize={11}
                    tickLine={false}
                    axisLine={{ stroke: 'rgba(255,255,255,0.08)' }}
                    fontFamily="JetBrains Mono"
                    minTickGap={28}
                  />
                  <YAxis
                    stroke="#757575"
                    fontSize={11}
                    width={56}
                    tickFormatter={(v) => `${Number(v) > 0 ? '+' : ''}${Number(v).toFixed(2)}%`}
                    tickLine={false}
                    axisLine={{ stroke: 'rgba(255,255,255,0.08)' }}
                    fontFamily="JetBrains Mono"
                  />
                  <ReferenceLine y={0} stroke="rgba(255,255,255,0.25)" strokeWidth={1} />
                  <Tooltip
                    cursor={{ stroke: 'rgba(255,255,255,0.35)', strokeWidth: 1 }}
                    content={<CustomTooltip visibleSeries={visibleSeries} />}
                  />

                  {PAIRS.map((pair) =>
                    visibleKeysForPair(pair, filter).map((v) => {
                      const isHighlighted = highlightKey === v.key;
                      const isDimmed = highlightKey !== null && !isHighlighted;
                      return (
                        <Line
                          key={v.key}
                          type="monotone"
                          dataKey={v.key}
                          stroke={pair.color}
                          strokeWidth={isHighlighted ? 3 : (v.dashed ? 1.8 : 2.5)}
                          strokeDasharray={v.dashed ? '7 5' : undefined}
                          strokeOpacity={isDimmed ? 0.15 : 1}
                          dot={false}
                          activeDot={{ r: 4, stroke: '#f2efe8', strokeWidth: 1 }}
                          isAnimationActive={started}
                          animationDuration={1100}
                          connectNulls
                        />
                      );
                    })
                  )}

                  {lastRow &&
                    seriesWithValues.map((s) => {
                      const isHighlighted = highlightKey === s.key;
                      const isDimmed = highlightKey !== null && !isHighlighted;
                      const dy = labelDeltas.get(s.key) ?? 0;
                      return (
                        <ReferenceDot
                          key={`label-${s.key}`}
                          x={lastRow.date}
                          y={s.value}
                          r={isHighlighted ? 4 : 2.5}
                          fill={s.color}
                          stroke="none"
                          opacity={isDimmed ? 0.2 : 1}
                          label={{
                            value: s.name,
                            position: 'right',
                            fill: s.color,
                            fontSize: isHighlighted ? 11 : 10,
                            fontWeight: isHighlighted ? 700 : (s.dashed ? 500 : 600),
                            fontFamily: 'JetBrains Mono',
                            dy,
                          }}
                        />
                      );
                    })}
                </LineChart>
              </ResponsiveContainer>
            </div>

            {/* Clear, Concise Interactive Legend for All Visible Agents & Twins */}
            <div className="pt-2 border-t border-border-hairline space-y-2">
              <div className="flex items-center justify-between text-[11px] text-zinc-400 font-mono">
                <span className="font-semibold text-zinc-300">
                  {filter === 'ALL' ? 'All 10 Agents & Twins' : filter === 'LLM' ? 'AI Agents (5)' : 'Rules Twins (5)'}
                </span>
                <span className="text-zinc-500 hidden sm:inline">Click to pin · Hover to highlight curve</span>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                {seriesWithValues.map((s) => {
                  const isHighlighted = highlightKey === s.key;
                  const isDimmed = highlightKey !== null && !isHighlighted;
                  return (
                    <button
                      key={s.key}
                      type="button"
                      onMouseEnter={() => setHoveredKey(s.key)}
                      onMouseLeave={() => setHoveredKey(null)}
                      onClick={() => setPinnedKey((prev) => (prev === s.key ? null : s.key))}
                      className={cn(
                        'flex items-center gap-2 px-2.5 py-1.5 rounded border text-[11px] font-mono transition-all cursor-pointer',
                        isHighlighted
                          ? 'border-white/40 bg-white/[0.08] text-white shadow-sm ring-1 ring-white/20'
                          : isDimmed
                          ? 'border-border-hairline/40 text-zinc-600 opacity-40'
                          : 'border-border-hairline bg-surface-well/60 text-zinc-300 hover:text-white hover:border-white/25 hover:bg-white/[0.04]'
                      )}
                    >
                      {/* Swatch: Solid line for AI, Dashed line for Rules twin */}
                      <svg width="18" height="6" className="flex-shrink-0" aria-hidden="true">
                        <line
                          x1="0"
                          y1="3"
                          x2="18"
                          y2="3"
                          stroke={s.color}
                          strokeWidth={s.dashed ? 2 : 2.5}
                          strokeDasharray={s.dashed ? '4 3' : undefined}
                        />
                      </svg>
                      <span className={cn('font-semibold', s.dashed ? 'font-normal' : '')}>{s.name}</span>
                      <span
                        className={cn(
                          'tabular-nums text-[10px]',
                          s.value > 0 ? 'text-positive' : s.value < 0 ? 'text-negative' : 'text-zinc-500'
                        )}
                      >
                        {formatPct(s.value)}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="text-[12px] font-mono text-zinc-500 text-right">
              {rows[0]?.fullDate} → {rows[rows.length - 1]?.fullDate}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
