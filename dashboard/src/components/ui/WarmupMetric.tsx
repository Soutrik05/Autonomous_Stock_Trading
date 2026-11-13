import { cn } from '../../utils/cn';

interface WarmupMetricProps {
  value: number | string | null | undefined;
  closedTrades: number;
  sampleThreshold?: number;
  formatter?: (val: any) => string;
  fallbackText?: string;
  className?: string;
  warmupClassName?: string;
  compact?: boolean;
}

/**
 * Reusable treatment for metrics computed from an insufficient trade sample.
 * Below `sampleThreshold` (default: 30), renders a muted "Warming up · X/30 trades"
 * rather than a misleading zero or ungrounded decimal.
 */
export function WarmupMetric({
  value,
  closedTrades,
  sampleThreshold = 30,
  formatter = (v) => String(v),
  fallbackText = '—',
  className,
  warmupClassName,
  compact = false,
}: WarmupMetricProps) {
  const isWarmingUp = closedTrades < sampleThreshold;

  if (isWarmingUp) {
    if (compact) {
      return (
        <span
          title={`Sample warming up (${closedTrades}/${sampleThreshold} closed trades)`}
          className={cn("text-zinc-500 font-mono text-[11px] tabular-nums whitespace-nowrap", warmupClassName)}
        >
          Warming up · {closedTrades}/{sampleThreshold}
        </span>
      );
    }

    return (
      <span
        title={`Computed from an insufficient trade sample (${closedTrades}/${sampleThreshold} required closed trades)`}
        className={cn(
          "inline-flex items-center gap-1.5 text-zinc-500 font-mono text-xs tabular-nums whitespace-nowrap",
          warmupClassName
        )}
      >
        <span className="w-1.5 h-1.5 rounded-full bg-amber-500/60 animate-pulse flex-shrink-0" />
        <span>Warming up · {closedTrades}/{sampleThreshold} trades</span>
      </span>
    );
  }

  if (value === null || value === undefined) {
    return <span className={cn("text-zinc-600 font-mono text-xs", className)}>{fallbackText}</span>;
  }

  return <span className={cn("font-mono tabular-nums", className)}>{formatter(value)}</span>;
}

export default WarmupMetric;
