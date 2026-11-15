// @vitest-environment jsdom
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useCountUp } from './useCountUp';

const format = (n: number) => `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`;

describe('useCountUp', () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'requestAnimationFrame', 'cancelAnimationFrame'] });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('shows "-" for missing data and never animates', () => {
    const { result } = renderHook(() => useCountUp(undefined, format));
    expect(result.current).toBe('-');
    act(() => {
      vi.advanceTimersByTime(3000);
    });
    expect(result.current).toBe('-');
  });

  it('counts up and ends on the exact real formatted value', () => {
    const { result } = renderHook(() => useCountUp(4.25, format));
    // Before the 500ms start delay elapses, nothing has moved yet.
    act(() => {
      vi.advanceTimersByTime(400);
    });
    expect(result.current).not.toBe(format(4.25));
    // Run past delay + full 1500ms duration.
    act(() => {
      vi.advanceTimersByTime(2500);
    });
    expect(result.current).toBe(format(4.25));
  });

  it('does not replay the count-up on a later value change (just updates the text)', () => {
    const { result, rerender } = renderHook(({ value }) => useCountUp(value, format), {
      initialProps: { value: 4.25 },
    });
    act(() => {
      vi.advanceTimersByTime(2500);
    });
    expect(result.current).toBe(format(4.25));

    rerender({ value: 5.1 });
    // No animation delay/ramp this time -- updates immediately.
    expect(result.current).toBe(format(5.1));
  });
});
