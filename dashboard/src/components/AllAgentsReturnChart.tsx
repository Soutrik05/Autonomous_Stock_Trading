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
  const [hoveredBase, setHoveredBase] = useState<string | null>(null);
  const [pinnedBase, setPinnedBase] = useState<string | null>(null);
  const introDone = useIntroDone();
  const reducedMotion = usePrefersReducedMotion();

  const highlightBase = pinnedBase ?? hoveredBase;

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
    visibleKeysForPair(pair, filter).map((v) => ({ key: v.key, id: v.id, color: pair.color }))
  );

  // End-of-line labels: show all when there's room (<=5 visible lines), otherwise only the
  // top 3 and bottom 1 by final value -- the rest are still fully available on hover.
  const lastRow = rows.length > 0 ? rows[rows.length - 1] : null;
  const endLabelTargets = (() => {
    if (!lastRow) return new Set<string>();
    const withValues = visibleSeries
      .map((s) => ({ ...s, value: lastRow[s.key] as number | null }))
      .filter((s): s is { key: string; id: string; color: string; value: number } => s.value !== null);
    if (withValues.length <= 5) return new Set(withValues.map((s) => s.key));
    const sorted = [...withValues].sort((a, b) => b.value - a.value);
    const picked = [...sorted.slice(0, 3), sorted[sorted.length - 1]];
    return new Set(picked.map((s) => s.key));
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
                <LineChart data={rows} margin={{ top: 10, right: 90, left: 8, bottom: 0 }}>
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
                      const dimmed = highlightBase !== null && highlightBase !== pair.base;
                      return (
                        <Line
                          key={v.key}
                          type="monotone"
                          dataKey={v.key}
                          stroke={pair.color}
                          strokeWidth={v.dashed ? 1.8 : 2.5}
                          strokeDasharray={v.dashed ? '7 5' : undefined}
                          strokeOpacity={dimmed ? 0.15 : 1}
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
                    visibleSeries
                      .filter((s) => endLabelTargets.has(s.key))
                      .map((s) => {
                        const value = lastRow[s.key] as number | null;
                        if (value === null) return null;
                        return (
                          <ReferenceDot
                            key={`label-${s.key}`}
                            x={lastRow.date}
                            y={value}
                            r={3}
                            fill={s.color}
                            stroke="none"
                            label={{
                              value: getAgentName(s.id),
                              position: 'right',
                              fill: s.color,
                              fontSize: 10,
                              fontFamily: 'JetBrains Mono',
                            }}
                          />
                        );
                      })}
                </LineChart>
              </ResponsiveContainer>
            </div>

            {/* Legend: 5 chips, one per pair -- hover/click pins the highlight */}
            <div className="flex flex-wrap items-center gap-2 pt-1">
              {PAIRS.map((pair) => (
                <button
                  key={pair.base}
                  type="button"
                  onMouseEnter={() => setHoveredBase(pair.base)}
                  onMouseLeave={() => setHoveredBase(null)}
                  onClick={() => setPinnedBase((prev) => (prev === pair.base ? null : pair.base))}
                  className={cn(
                    'flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-[11px] font-mono transition-colors cursor-pointer',
                    pinnedBase === pair.base
                      ? 'border-white/30 bg-white/[0.06] text-white'
                      : 'border-border-hairline text-zinc-400 hover:text-white hover:bg-white/[0.03]'
                  )}
                >
                  <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: pair.color }} />
                  {getAgentName(pair.llmId)}
                </button>
              ))}
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
