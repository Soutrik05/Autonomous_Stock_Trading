import React from 'react';
import { cn } from '../../utils/cn';
import PageTitle from './PageTitle';

interface SectionHeaderProps {
  title: string;
  subtitle?: string;
  tag?: string;
  className?: string;
  children?: React.ReactNode;
  /** 'page' renders `title` as the shared PageTitle (Red Hat Display 700 + green cursor
   * hover) for a page's own main heading (Leaderboard, Telemetry); omit for every other,
   * plain section heading elsewhere on a page -- those are unchanged. */
  variant?: 'default' | 'page';
}

export const SectionHeader: React.FC<SectionHeaderProps> = ({
  title,
  subtitle,
  tag,
  className,
  children,
  variant = 'default',
}) => {
  return (
    <div className={cn('space-y-1.5', className)}>
      {tag && (
        <div className="flex items-center gap-2 text-[11px] font-mono text-brand-blue-text">
          <span>{tag}</span>
        </div>
      )}
      <div className="flex flex-col sm:flex-row sm:items-baseline sm:justify-between gap-2">
        {variant === 'page' ? (
          <PageTitle>{title}</PageTitle>
        ) : (
          <h2 className="font-display text-3xl sm:text-[34px] font-medium tracking-tight text-white leading-tight">
            {title}
          </h2>
        )}
        {children}
      </div>
      {subtitle && (
        <p className="text-sm sm:text-base font-mono text-zinc-400">
          {subtitle}
        </p>
      )}
    </div>
  );
};

