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
        className="inline-flex items-center gap-1 px-2 py-0.5 rounded-[2px] text-xs font-mono font-medium bg-[#F3EFE6] text-[#8A7441] border border-[#D6C7A1]"
        title={`Small sample alert: Strategy has only ${closedTradesCount} closed trades (minimum ${threshold} required for statistical significance).`}
      >
        <AlertTriangle className="w-3 h-3 text-[#8A7441]" />
        Provisional ({closedTradesCount}/{threshold})
      </span>
    );
  }

  return (
    <div className="callout-panel flex items-start gap-3 p-4 text-xs font-sans">
      <AlertTriangle className="w-4 h-4 text-[#8A7441] flex-shrink-0 mt-0.5" />
      <div>
        <p className="font-serif font-bold text-[#151B26] text-sm">
          Small-sample notice (Statistical guardrail)
        </p>
        <p className="mt-1 text-[#475060] leading-relaxed">
          This agent currently has <strong>{closedTradesCount}</strong> closed trades, which is below the statistical threshold of <strong>{threshold}</strong> trades. Performance metrics (Sharpe ratio, win rate, return distribution) must be treated as <strong>provisional</strong> and may reflect regime variance rather than enduring alpha.
        </p>
      </div>
    </div>
  );
}
