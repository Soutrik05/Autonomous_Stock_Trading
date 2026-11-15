import { useEffect, useRef, useState } from 'react';
import { usePrefersReducedMotion } from './usePrefersReducedMotion';

const DEFAULT_DURATION_MS = 1500;
const DEFAULT_DELAY_MS = 500;

function easeOutCubic(t: number): number {
  return 1 - Math.pow(1 - t, 3);
}

function isRealNumber(v: unknown): v is number {
  return typeof v === 'number' && !Number.isNaN(v);
}

/**
 * Counts a number up from 0 to `value` the first time a real value appears, using the
 * given formatter at every frame (so sign/grouping/decimals always come from the real
 * formatter, never an invented display format). Later changes to `value` do not replay
 * the count-up -- they just update the displayed text immediately (see useFlashOnChange
 * for drawing attention to that kind of update instead). Missing data (null/undefined/NaN)
 * always renders as "-", never 0 or a stale animated number. Respects reduced motion by
 * skipping straight to the final formatted value.
 */
export function useCountUp(
  value: number | null | undefined,
  format: (n: number) => string,
  options: { duration?: number; delay?: number } = {}
): string {
  const { duration = DEFAULT_DURATION_MS, delay = DEFAULT_DELAY_MS } = options;
  const reducedMotion = usePrefersReducedMotion();
  const hasAnimatedRef = useRef(false);
  const [display, setDisplay] = useState<string>(() => {
    if (!isRealNumber(value)) return '-';
    if (reducedMotion) {
      hasAnimatedRef.current = true;
      return format(value);
    }
    return format(0);
  });

  useEffect(() => {
    if (!isRealNumber(value)) {
      setDisplay('-');
      return;
    }

    if (hasAnimatedRef.current || reducedMotion) {
      hasAnimatedRef.current = true;
      setDisplay(format(value));
      return;
    }

    hasAnimatedRef.current = true;
    const target = value;
    let rafId: number | null = null;
    let start: number | null = null;

    const timeoutId = setTimeout(() => {
      const step = (ts: number) => {
        if (start === null) start = ts;
        const elapsed = ts - start;
        const t = Math.min(1, elapsed / duration);
        setDisplay(format(target * easeOutCubic(t)));
        if (t < 1) {
          rafId = requestAnimationFrame(step);
        } else {
          setDisplay(format(target));
        }
      };
      rafId = requestAnimationFrame(step);
    }, delay);

    return () => {
      clearTimeout(timeoutId);
      if (rafId !== null) cancelAnimationFrame(rafId);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  return display;
}
