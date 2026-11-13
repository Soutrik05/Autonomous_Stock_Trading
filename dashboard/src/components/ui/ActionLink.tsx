import React from 'react';
import { Link } from 'react-router-dom';
import { cn } from '../../utils/cn';

interface ActionLinkProps {
  to: string;
  children: React.ReactNode;
  variant?: 'primary' | 'secondary' | 'subdued';
  className?: string;
}

export const ActionLink: React.FC<ActionLinkProps> = ({
  to,
  children,
  variant = 'secondary',
  className,
}) => {
  const variantStyles = {
    primary: 'text-white hover:text-accent font-medium',
    secondary: 'text-zinc-400 hover:text-white font-medium',
    subdued: 'text-zinc-500 hover:text-zinc-300 font-normal text-xs',
  };

  return (
    <Link
      to={to}
      className={cn(
        'inline-flex items-center gap-1.5 transition-colors cursor-pointer group',
        variantStyles[variant],
        className
      )}
    >
      <span>{children}</span>
      <span className="font-mono text-xs transition-transform group-hover:translate-x-0.5 select-none">
        &rarr;
      </span>
    </Link>
  );
};

