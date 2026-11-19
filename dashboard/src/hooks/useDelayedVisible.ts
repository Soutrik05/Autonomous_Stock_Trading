import { useEffect, useRef, useState } from 'react';

/**
 * Shows `loading` only after a 150ms delay (so a fetch that resolves almost instantly never
 * flashes a skeleton), and once shown, keeps it visible for at least 300ms (so it never
 * flickers for a single frame on a slightly-slower-than-150ms response).
 */
export function useDelayedVisible(loading: boolean, delayMs = 150, minVisibleMs = 300): boolean {
  const [visible, setVisible] = useState(false);
  const shownAtRef = useRef<number | null>(null);

  useEffect(() => {
    if (loading) {
      const id = window.setTimeout(() => {
        shownAtRef.current = performance.now();
        setVisible(true);
      }, delayMs);
      return () => window.clearTimeout(id);
    }

    if (!visible) return;
    const shownFor = shownAtRef.current !== null ? performance.now() - shownAtRef.current : minVisibleMs;
    const remaining = Math.max(0, minVisibleMs - shownFor);
    const id = window.setTimeout(() => {
      shownAtRef.current = null;
      setVisible(false);
    }, remaining);
    return () => window.clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading]);

  return visible;
}
