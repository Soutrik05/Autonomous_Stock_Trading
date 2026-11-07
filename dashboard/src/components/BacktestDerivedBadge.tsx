import { ShieldAlert } from 'lucide-react';

interface BacktestDerivedBadgeProps {
  size?: 'sm' | 'md';
}

export default function BacktestDerivedBadge({ size = 'sm' }: BacktestDerivedBadgeProps) {
  const sizeClasses = size === 'sm' ? 'text-[11px] px-2 py-0.5' : 'text-xs px-2.5 py-1';

  return (
    <span className={`inline-flex items-center gap-1 font-semibold uppercase tracking-wider rounded border bg-purple-50 text-purple-800 border-purple-200 dark:bg-purple-950/50 dark:text-purple-300 dark:border-purple-800 ${sizeClasses}`}
          title="Mandatory Guardrail: These metrics are derived from historical backtesting against daily OHLCV and are isolated from live paper-trading results.">
      <ShieldAlert className="w-3.5 h-3.5 text-purple-600 dark:text-purple-400" />
      BACKTEST_DERIVED
    </span>
  );
}
