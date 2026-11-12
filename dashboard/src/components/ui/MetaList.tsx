import React from 'react';
import { cn } from '../../utils/cn';

export interface MetaItem {
  label?: string;
  value: string;
}

interface MetaListProps {
  items: (string | MetaItem)[];
  className?: string;
  separator?: string;
}

export const MetaList: React.FC<MetaListProps> = ({
  items,
  className,
  separator = '·',
}) => {
  return (
    <div className={cn('text-[11px] sm:text-xs font-mono text-zinc-400 flex flex-wrap items-center gap-y-1', className)}>
      {items.map((item, i) => {
        const isObj = typeof item === 'object' && item !== null;
        const label = isObj ? item.label : undefined;
        const val = isObj ? item.value : item;

        return (
          <span key={i} className="inline-flex items-center">
            {i > 0 && <span className="text-zinc-600 mx-2 select-none">{separator}</span>}
            {label && <span className="text-zinc-500 uppercase tracking-wider mr-1">{label}:</span>}
            <span className={cn(label ? 'text-zinc-200' : (i % 2 === 1 ? 'text-zinc-300' : 'text-zinc-400'))}>
              {val}
            </span>
          </span>
        );
      })}
    </div>
  );
};

