interface MetricBadgeProps {
  label: string;
  value: string | number;
  variant?: 'neutral' | 'success' | 'warning' | 'danger' | 'accent';
  size?: 'sm' | 'md';
}

export default function MetricBadge({ label, value, variant = 'neutral', size = 'sm' }: MetricBadgeProps) {
  const variantStyles = {
    neutral: 'bg-[#F6F4EF] text-[#475060] border-[#DCD7CC]',
    success: 'bg-[#EBF5F0] text-[#1E6548] border-[#A3D4BE]',
    warning: 'bg-[#F3EFE6] text-[#8A7441] border-[#D6C7A1]',
    danger: 'bg-[#FBF0F0] text-[#933835] border-[#E5ACAA]',
    accent: 'bg-[#EDF2F9] text-[#2A4B7C] border-[#B9C9E1]',
  };

  const sizeStyles = {
    sm: 'text-xs px-2.5 py-1',
    md: 'text-sm px-3 py-1.5',
  };

  return (
    <span className={`inline-flex items-center gap-1.5 font-mono rounded-[2px] border ${variantStyles[variant]} ${sizeStyles[size]}`}>
      <span className="text-[#7C8698] font-normal">{label}:</span>
      <span className="font-semibold">{value}</span>
    </span>
  );
}
