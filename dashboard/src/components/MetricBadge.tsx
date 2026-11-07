interface MetricBadgeProps {
  label: string;
  value: string | number;
  variant?: 'neutral' | 'success' | 'warning' | 'danger' | 'accent';
  size?: 'sm' | 'md';
}

export default function MetricBadge({ label, value, variant = 'neutral', size = 'sm' }: MetricBadgeProps) {
  const variantStyles = {
    neutral: 'bg-stone-100 text-stone-800 border-stone-200 dark:bg-stone-800 dark:text-stone-200 dark:border-stone-700',
    success: 'bg-emerald-50 text-emerald-800 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800',
    warning: 'bg-amber-50 text-amber-800 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-800',
    danger: 'bg-rose-50 text-rose-800 border-rose-200 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-800',
    accent: 'bg-indigo-50 text-indigo-800 border-indigo-200 dark:bg-indigo-950/40 dark:text-indigo-300 dark:border-indigo-800',
  };

  const sizeStyles = {
    sm: 'text-xs px-2.5 py-1',
    md: 'text-sm px-3 py-1.5',
  };

  return (
    <span className={`inline-flex items-center gap-1.5 font-medium rounded-md border ${variantStyles[variant]} ${sizeStyles[size]}`}>
      <span className="opacity-70">{label}:</span>
      <span className="font-semibold">{value}</span>
    </span>
  );
}
