import type { CSSProperties } from 'react';

/**
 * Shared skeleton-shimmer placeholder (see `.skeleton-shimmer` in index.css, and
 * `useDelayedVisible` for the 150ms-delay/300ms-minimum timing). There was no shimmer
 * component in the codebase yet -- this is the first one, built for the "no loading screen
 * on refresh" rule: a genuine first load (no cached data) shows this instead of a
 * spinner/blank area, everything else (a refresh with cached data) skips straight to the
 * real content.
 */
export function SkeletonBlock({ className = '', style }: { className?: string; style?: CSSProperties }) {
  return <div className={`skeleton-shimmer ${className}`.trim()} style={style} />;
}
