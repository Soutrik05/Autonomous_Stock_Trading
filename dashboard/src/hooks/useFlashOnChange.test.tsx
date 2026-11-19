// @vitest-environment jsdom
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useFlashOnChange } from './useFlashOnChange';

describe('useFlashOnChange', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('does not flash on first mount', () => {
    const { result } = renderHook(() => useFlashOnChange(100));
    expect(result.current).toBe('');
  });

  it('does not flash when going from missing data ("-") to a real value', () => {
    const { result, rerender } = renderHook(({ value }) => useFlashOnChange(value), {
      initialProps: { value: undefined as number | undefined },
    });
    expect(result.current).toBe('');
    rerender({ value: 100 });
    expect(result.current).toBe('');
  });

  it('flashes up when a real value increases', () => {
    const { result, rerender } = renderHook(({ value }) => useFlashOnChange(value), {
      initialProps: { value: 100 },
    });
    rerender({ value: 110 });
    expect(result.current).toBe('flash-up');
    act(() => {
      vi.advanceTimersByTime(600);
    });
    expect(result.current).toBe('');
  });

  it('flashes down when a real value decreases', () => {
    const { result, rerender } = renderHook(({ value }) => useFlashOnChange(value), {
      initialProps: { value: 100 },
    });
    rerender({ value: 90 });
    expect(result.current).toBe('flash-down');
    act(() => {
      vi.advanceTimersByTime(600);
    });
    expect(result.current).toBe('');
  });

  it('does not flash when the value is unchanged', () => {
    const { result, rerender } = renderHook(({ value }) => useFlashOnChange(value), {
      initialProps: { value: 100 },
    });
    rerender({ value: 100 });
    expect(result.current).toBe('');
  });
});
