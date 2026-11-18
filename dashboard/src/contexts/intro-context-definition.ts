import { createContext } from 'react';

export interface IntroContextValue {
  introDone: boolean;
  markIntroDone: () => void;
}

// Defaults to true so any consumer rendered outside the provider (tests, Storybook, etc.)
// never blocks its own entrance animation waiting for an intro that isn't there.
export const IntroContext = createContext<IntroContextValue>({
  introDone: true,
  markIntroDone: () => {},
});
