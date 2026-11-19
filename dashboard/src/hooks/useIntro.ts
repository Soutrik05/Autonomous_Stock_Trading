import { useContext } from 'react';
import { IntroContext } from '../contexts/intro-context-definition';

export function useIntroDone(): boolean {
  return useContext(IntroContext).introDone;
}

export function useMarkIntroDone(): () => void {
  return useContext(IntroContext).markIntroDone;
}
