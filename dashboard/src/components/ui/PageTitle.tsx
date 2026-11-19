import type { CSSProperties, ReactNode, RefObject } from 'react';
import { useSpotlightHover } from '../../hooks/useSpotlightHover';

interface PageTitleProps {
  children: ReactNode;
  /** Plain-text version for the hover overlay's `data-text` (defaults to `children` when it's
   * already a plain string). Pass this explicitly when `children` isn't a bare string. */
  text?: string;
  as?: 'h1' | 'span';
  className?: string;
  style?: CSSProperties;
}

/**
 * The one shared page-heading style + green cursor-spotlight hover (same technique as the
 * header logo and the Agent Terminal's agent name -- see useSpotlightHover and
 * `.name-spotlight` in index.css): Red Hat Display 700, -0.02em letter-spacing, #f2efe8,
 * clamp(32px, 6vw, 44px) so it's ~44px on desktop and ~32px at 390px. Used for the main
 * heading of Leaderboard, Backtest, Telemetry and Comparison's two agent names; the Agent
 * Terminal's agent name uses the same `useSpotlightHover` hook directly since its size is
 * intentionally different (~48px, set by that page). Never used for the Home hero headline.
 */
export default function PageTitle({ children, text, as = 'h1', className = '', style }: PageTitleProps) {
  const { ref, onMouseMove } = useSpotlightHover<HTMLElement>();
  const dataText = text ?? (typeof children === 'string' ? children : undefined);
  const combinedClassName = `page-title name-spotlight ${className}`.trim();
  const elementRef = ref as RefObject<HTMLHeadingElement & HTMLSpanElement>;

  if (as === 'span') {
    return (
      <span
        ref={elementRef}
        onMouseMove={onMouseMove}
        data-text={dataText}
        className={combinedClassName}
        style={style}
      >
        {children}
      </span>
    );
  }

  return (
    <h1
      ref={elementRef}
      onMouseMove={onMouseMove}
      data-text={dataText}
      className={combinedClassName}
      style={style}
    >
      {children}
    </h1>
  );
}
