import React from 'react';
import { cn } from '../../utils/cn';

interface CategoryBadgeProps {
  type: 'LLM' | 'RULES' | 'SYSTEM' | string;
  className?: string;
}

export const CategoryBadge: React.FC<CategoryBadgeProps> = ({ type, className }) => {
  const normalized = type.toUpperCase();
  const isRules = normalized.includes('RULES') || normalized.startsWith('BASELINE');

  return (
    <span
      className={cn(
        'px-1.5 py-0.2 rounded border text-[9px] font-mono uppercase tracking-wider flex-shrink-0 transition-colors',
        isRules
          ? 'border-white/15 text-zinc-400 bg-white/[0.02]'
          : 'border-white/20 text-zinc-300 bg-white/[0.04]',
        className
      )}
    >
      {isRules ? 'Rules' : 'LLM'}
    </span>
  );
};

