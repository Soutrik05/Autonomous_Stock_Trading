import { AlertTriangle } from 'lucide-react';

interface SmallSampleNoticeProps {
  closedTradesCount: number;
  threshold?: number;
  inline?: boolean;
}

export default function SmallSampleNotice({ closedTradesCount, threshold = 30, inline = false }: SmallSampleNoticeProps) {
  if (closedTradesCount >= threshold) {
    return null;
  }

  if (inline) {
    return (
      <span
        className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-mono font-medium bg-amber-500/10 text-amber-300 border border-amber-500/30"
        title={`Small sample alert: Strategy has only ${closedTradesCount} closed trades (minimum ${threshold} required for statistical significance).`}
      >
        <AlertTriangle className="w-3 h-3 text-amber-400" />
        Provisional ({closedTradesCount}/{threshold})
      </span>
    );
  }

  return (
    <div className="arena-glass flex items-start gap-3.5 p-4 text-xs font-sans border-amber-500/30 bg-amber-500/5">
      <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
      <div>
        <p className="font-bold text-amber-300 text-sm">
          Small-Sample Notice (Statistical Guardrail)
        </p>
        <p className="mt-1 text-slate-300 leading-relaxed">
          This agent currently has <strong>{closedTradesCount}</strong> closed trades, which is below the statistical threshold of <strong>{threshold}</strong> trades. Performance metrics (Sharpe ratio, win rate, return distribution) must be treated as <strong>provisional</strong> and may reflect regime variance rather than enduring alpha.
        </p>
      </div>
    </div>
  );
}
