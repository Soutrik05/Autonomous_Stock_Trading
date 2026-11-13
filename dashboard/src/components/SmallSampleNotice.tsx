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
    <div className="border-l-2 border-accent pl-4 py-1 text-xs font-mono text-zinc-400 space-y-1">
      <div className="flex items-center gap-2">
        <span className="text-accent font-semibold text-[11px]">
          Provisional Sample Notice
        </span>
        <span className="text-zinc-600">·</span>
        <span className="text-zinc-400">
          {closedTradesCount} of {threshold} closed trades
        </span>
      </div>
      <p className="text-zinc-400 font-sans leading-relaxed text-xs">
        Performance metrics must be treated as provisional until the sample reaches the statistical significance threshold of {threshold} closed trades.
      </p>
    </div>
  );
}
