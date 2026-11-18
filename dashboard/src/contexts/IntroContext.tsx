import { useState, type ReactNode } from 'react';
import { IntroContext } from './intro-context-definition';

/** Shared "has the brand intro finished (or been skipped / never shown)?" flag. Entrance
 * animations that would otherwise play immediately on mount (the Home hero reveal, the Top 3
 * standings step-up) read this via useIntroDone() (src/hooks/useIntro.ts) and simply wait for
 * it to flip true -- the animations themselves are unchanged, only their start is gated. */
export function IntroProvider({ children }: { children: ReactNode }) {
  const [introDone, setIntroDone] = useState(false);
  return (
    <IntroContext.Provider value={{ introDone, markIntroDone: () => setIntroDone(true) }}>
      {children}
    </IntroContext.Provider>
  );
}
