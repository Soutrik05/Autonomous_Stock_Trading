import { useRef } from 'react';
import type { MouseEvent } from 'react';

/**
 * The cursor-tracked green spotlight technique shared by the brand wordmark (Logo.tsx), the
 * Agent Terminal's agent name, and every shared page heading (PageTitle.tsx): writes
 * --mx/--my (px, relative to the element) via requestAnimationFrame on mouse move, which the
 * `.name-spotlight::after` CSS (index.css) uses to clip a green radial gradient to the text.
 * One place for the handler so every consumer behaves identically.
 */
export function useSpotlightHover<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const rafRef = useRef<number | null>(null);

  const onMouseMove = (e: MouseEvent<T>) => {
    const el = ref.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    rafRef.current = requestAnimationFrame(() => {
      el.style.setProperty('--mx', `${mx}px`);
      el.style.setProperty('--my', `${my}px`);
    });
  };

  return { ref, onMouseMove };
}
