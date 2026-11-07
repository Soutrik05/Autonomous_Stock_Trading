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
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-300 dark:bg-amber-950/60 dark:text-amber-300 dark:border-amber-800"
            title={`Small Sample Alert: Strategy has only ${closedTradesCount} closed trades (minimum 30 required for statistical significance).`}>
        <AlertTriangle className="w-3 h-3 text-amber-600 dark:text-amber-400" />
        PROVISIONAL ({closedTradesCount}/{threshold})
      </span>
    );
  }

  return (
    <div className="flex items-start gap-3 p-4 rounded-lg bg-amber-50 border border-amber-200 dark:bg-amber-950/30 dark:border-amber-900/60 text-amber-900 dark:text-amber-200 text-sm">
      <AlertTriangle className="w-5 h-5 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" />
      <div>
        <p className="font-semibold text-amber-950 dark:text-amber-100">
          Small-Sample Notice (Mandatory Plan Guardrail)
        </p>
        <p className="mt-1 text-amber-800/90 dark:text-amber-300/90">
          This agent currently has <strong>{closedTradesCount}</strong> closed trades, which is below the statistical threshold of <strong>{threshold}</strong> trades. Performance metrics (Sharpe ratio, win rate, return distribution) must be treated as <strong>PROVISIONAL</strong> and may reflect regime variance rather than enduring alpha.
        </p>
      </div>
    </div>
  );
}
