import { ShieldAlert } from 'lucide-react';

interface BacktestDerivedBadgeProps {
  size?: 'sm' | 'md';
}

export default function BacktestDerivedBadge({ size = 'sm' }: BacktestDerivedBadgeProps) {
  const sizeClasses = size === 'sm' ? 'text-[11px] px-2 py-0.5' : 'text-xs px-2.5 py-1';

  return (
    <span
      className={`inline-flex items-center gap-1 font-mono font-medium rounded-[2px] border bg-[#F4F0F9] text-[#5E4B7A] border-[#D3C6E5] ${sizeClasses}`}
      title="Mandatory Guardrail: These metrics are derived from historical backtesting against daily OHLCV and are isolated from live paper-trading results."
    >
      <ShieldAlert className="w-3.5 h-3.5 text-[#5E4B7A]" />
      Backtest derived
    </span>
  );
}
