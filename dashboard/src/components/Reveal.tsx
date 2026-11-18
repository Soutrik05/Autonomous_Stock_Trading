import { useEffect, useRef, useState, type ReactNode, type ElementType } from 'react';
import { usePrefersReducedMotion } from '../hooks/usePrefersReducedMotion';
import { useIntroDone } from '../hooks/useIntro';

interface RevealProps {
  children: ReactNode;
  /** 'immediate' animates on mount (for above-the-fold content); 'onscroll' (default) waits
   * for the element to enter the viewport via IntersectionObserver, once. */
  mode?: 'immediate' | 'onscroll';
  delayMs?: number;
  className?: string;
  as?: ElementType;
}

/** Fades in + slides up 18px, once per mount. Respects prefers-reduced-motion (shows final
 * state immediately, no observer, no transition). Never re-triggers on data refresh since
 * visibility is local component state untouched by prop/data changes. */
export default function Reveal({ children, mode = 'onscroll', delayMs = 0, className = '', as: Tag = 'div' }: RevealProps) {
  const ref = useRef<HTMLDivElement>(null);
  const reducedMotion = usePrefersReducedMotion();
  const introDone = useIntroDone();
  const [visible, setVisible] = useState(reducedMotion);

  useEffect(() => {
    if (reducedMotion) {
      setVisible(true);
      return;
    }
    if (mode === 'immediate') {
      // Above-the-fold content would otherwise start revealing underneath the brand intro
      // overlay; wait for it to finish (or be skipped) before playing, same animation either way.
      if (!introDone) return;
      const id = requestAnimationFrame(() => setVisible(true));
      return () => cancelAnimationFrame(id);
    }
    const el = ref.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setVisible(true);
            observer.unobserve(entry.target);
          }
        }
      },
      { threshold: 0.15 }
    );
    observer.observe(el);
    return () => observer.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reducedMotion, introDone]);

  return (
    <Tag
      ref={ref}
      className={`reveal ${visible ? 'reveal--visible' : ''} ${className}`}
      style={{ transitionDelay: visible ? `${delayMs}ms` : undefined }}
    >
      {children}
    </Tag>
  );
}
