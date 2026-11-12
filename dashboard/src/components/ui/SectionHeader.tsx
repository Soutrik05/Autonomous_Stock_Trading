import React from 'react';
import { cn } from '../../utils/cn';

interface SectionHeaderProps {
  title: string;
  subtitle?: string;
  tag?: string;
  className?: string;
  children?: React.ReactNode;
}

export const SectionHeader: React.FC<SectionHeaderProps> = ({
  title,
  subtitle,
  tag,
  className,
  children,
}) => {
  return (
    <div className={cn('space-y-1.5', className)}>
      {tag && (
        <div className="flex items-center gap-2 text-[11px] font-mono text-accent uppercase tracking-wider">
          <span>{tag}</span>
        </div>
      )}
      <div className="flex flex-col sm:flex-row sm:items-baseline sm:justify-between gap-2">
        <h2 className="font-display text-2xl sm:text-3xl font-medium tracking-tight text-white">
          {title}
        </h2>
        {children}
      </div>
      {subtitle && (
        <p className="text-xs font-mono text-zinc-400">
          {subtitle}
        </p>
      )}
    </div>
  );
};

