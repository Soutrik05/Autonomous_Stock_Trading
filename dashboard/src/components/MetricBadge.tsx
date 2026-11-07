interface MetricBadgeProps {
  label: string;
  value: string | number;
  variant?: 'neutral' | 'success' | 'warning' | 'danger' | 'accent';
  size?: 'sm' | 'md';
}

export default function MetricBadge({ label, value, variant = 'neutral', size = 'sm' }: MetricBadgeProps) {
  const variantStyles = {
    neutral: 'bg-white/5 text-slate-300 border-white/10',
    success: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
    warning: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
    danger: 'bg-rose-500/10 text-rose-400 border-rose-500/30',
    accent: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30',
  };

  const sizeStyles = {
    sm: 'text-xs px-2.5 py-1',
    md: 'text-sm px-3 py-1.5',
  };

  return (
    <span className={`inline-flex items-center gap-1.5 font-mono rounded border ${variantStyles[variant]} ${sizeStyles[size]}`}>
      <span className="text-slate-400 font-normal">{label}:</span>
      <span className="font-semibold text-white">{value}</span>
    </span>
  );
}
