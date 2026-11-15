import { useEffect, useState } from 'react';
import { usePrefersReducedMotion } from './usePrefersReducedMotion';

const FLASH_DURATION_MS = 600;

function isRealNumber(v: unknown): v is number {
  return typeof v === 'number' && !Number.isNaN(v);
}

/**
 * Returns 'flash-up' | 'flash-down' | '' for ~600ms whenever `value` changes from one real
 * number to a different real number. Never flashes on first mount, never on a "-" (missing
 * data) to a real value transition (that's the count-up's job instead), and never under
 * prefers-reduced-motion.
 */
export function useFlashOnChange(value: number | null | undefined): string {
  const reducedMotion = usePrefersReducedMotion();
  const [prevValue, setPrevValue] = useState(value);
  const [sawReal, setSawReal] = useState(() => isRealNumber(value));
  const [flashClass, setFlashClass] = useState('');

  // React's documented "adjusting state when a prop changes" pattern: detect the change
  // during render (state only, no refs) rather than in an effect, so no setState call
  // runs in an effect body and no ref is written during render.
  if (prevValue !== value) {
    const prevWasReal = isRealNumber(prevValue);
    const nowIsReal = isRealNumber(value);

    setFlashClass(
      nowIsReal && prevWasReal && sawReal && !reducedMotion
        ? value > (prevValue as number)
          ? 'flash-up'
          : 'flash-down'
        : ''
    );
    if (nowIsReal && !sawReal) setSawReal(true);
    setPrevValue(value);
  }

  // Auto-clear the flash after FLASH_DURATION_MS; this setState runs inside a timer
  // callback, not synchronously in the effect body, so it's not a cascading render.
  useEffect(() => {
    if (!flashClass) return;
    const id = setTimeout(() => setFlashClass(''), FLASH_DURATION_MS);
    return () => clearTimeout(id);
  }, [flashClass]);

  return flashClass;
}
