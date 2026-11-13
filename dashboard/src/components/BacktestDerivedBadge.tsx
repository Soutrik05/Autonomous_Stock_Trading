import { ShieldAlert } from 'lucide-react';

interface BacktestDerivedBadgeProps {
  size?: 'sm' | 'md';
}

export default function BacktestDerivedBadge({ size = 'sm' }: BacktestDerivedBadgeProps) {
  const sizeClasses = size === 'sm' ? 'text-[11px] px-2 py-0.5' : 'text-xs px-2.5 py-1';

  return (
    <span
      className={`inline-flex items-center gap-1.5 font-mono font-medium rounded border bg-purple-500/15 text-purple-300 border-purple-500/30 ${sizeClasses}`}
      title="Mandatory Guardrail: These metrics are derived from historical backtesting against daily OHLCV and are isolated from live paper-trading results."
    >
      <ShieldAlert className="w-3.5 h-3.5 text-purple-400" />
      Backtest Derived
    </span>
  );
}
