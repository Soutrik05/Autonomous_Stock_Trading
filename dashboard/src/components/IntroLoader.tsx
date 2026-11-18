import { useEffect, useState } from 'react';
import { usePrefersReducedMotion } from '../hooks/usePrefersReducedMotion';
import { useMarkIntroDone } from '../hooks/useIntro';
import './IntroLoader.css';

const SESSION_KEY = 'stockminds_intro_seen';
const FULL_NAME = 'StockMinds';
const FULL_TAGLINE_PART1 = 'five minds, ';
const FULL_TAGLINE_PART2 = 'one market';

/** Every timed offset (ms from mount) and duration in one place, so the whole sequence can be
 * re-tuned without hunting through the component. Total runtime = slideStart + slideDur = 3.0s.
 * Exit: hold -> the whole group (name/tagline/underline) fades + blurs + drifts up into the
 * black together -> the black overlay itself slides up off the screen. */
const TIMELINE = {
  nameStart: 100, nameDur: 500, // 0.10 - 0.60
  tag1Start: 600, tag1Dur: 350, // 0.60 - 0.95
  tag2Start: 950, tag2Dur: 350, // 0.95 - 1.30
  underlineStart: 1300, underlineDur: 300, // 1.30 - 1.60
  // 1.60 - 2.00 is just a hold, nothing fires
  fadeStart: 2000, fadeDur: 450, // 2.00 - 2.45
  slideStart: 2450, slideDur: 550, // 2.45 - 3.00
  skipFadeDur: 200,
  skipSlideDur: 250,
};

function hasSeenIntroThisSession(): boolean {
  try {
    return sessionStorage.getItem(SESSION_KEY) === 'true';
  } catch {
    // Storage unavailable (private mode edge cases, etc.) -- fall through and play it once
    // for this page load rather than erroring out.
    return false;
  }
}

function markSeenThisSession(): void {
  try {
    sessionStorage.setItem(SESSION_KEY, 'true');
  } catch {
    // Ignore -- worst case the intro plays again, which is the safe failure direction.
  }
}

interface Phases {
  name: boolean;
  tag1: boolean;
  tag2: boolean;
  underline: boolean;
  fading: boolean;
  sliding: boolean;
}

const INITIAL_PHASES: Phases = {
  name: false,
  tag1: false,
  tag2: false,
  underline: false,
  fading: false,
  sliding: false,
};

/**
 * Full-screen, 3-second brand intro that plays once per browser session, then melts into black
 * and slides up to reveal the real page underneath (which has already mounted and started
 * fetching its own data -- this overlay never blocks that). Driven by a single
 * requestAnimationFrame loop measuring elapsed time since mount against the fixed millisecond
 * offsets in TIMELINE, so the sequence (name in -> "five minds," in -> "one market" in, same
 * way -> underline draws -> hold -> the whole group fades/blurs/drifts into black -> the
 * overlay itself slides up) always lands at the same times regardless of frame rate. Skippable
 * by click/tap/key (same exit, faster); respects prefers-reduced-motion (never shown at all).
 */
export default function IntroLoader() {
  const reducedMotion = usePrefersReducedMotion();
  const markIntroDone = useMarkIntroDone();

  // Decide once, synchronously, whether this mount should play at all.
  const [shouldPlay] = useState(() => !reducedMotion && !hasSeenIntroThisSession());
  const [mounted, setMounted] = useState(shouldPlay);
  const [phases, setPhases] = useState<Phases>(INITIAL_PHASES);
  const [fast, setFast] = useState(false);

  useEffect(() => {
    if (!shouldPlay) {
      // Nothing to play (already seen this session, or reduced motion): the rest of the app
      // must not wait for an intro that will never run.
      markIntroDone();
      return;
    }

    document.body.style.overflow = 'hidden';

    let rafId = 0;
    let finished = false;
    let fadeTimeoutId = 0;
    let slideTimeoutId = 0;
    const startedAt = performance.now();
    // Mirrors BubbleBackground's own pause-while-hidden guard: a backgrounded tab must not
    // let requestAnimationFrame starve and then "catch up" by jumping the whole timeline
    // forward in one frame when it becomes visible again -- the clock itself pauses instead.
    let hiddenSinceMs: number | null = document.hidden ? performance.now() : null;
    let totalHiddenMs = 0;
    function handleVisibility() {
      if (document.hidden) {
        hiddenSinceMs = performance.now();
      } else if (hiddenSinceMs !== null) {
        totalHiddenMs += performance.now() - hiddenSinceMs;
        hiddenSinceMs = null;
      }
    }
    document.addEventListener('visibilitychange', handleVisibility);
    const fired = {
      name: false,
      tag1: false,
      tag2: false,
      underline: false,
      fade: false,
      slide: false,
    };

    function finish() {
      if (finished) return;
      finished = true;
      markSeenThisSession();
      document.body.style.overflow = '';
      markIntroDone();
      setMounted(false);
    }

    function tick() {
      const now = performance.now();
      const currentlyHiddenMs = hiddenSinceMs !== null ? now - hiddenSinceMs : 0;
      const elapsed = now - startedAt - totalHiddenMs - currentlyHiddenMs;

      if (document.hidden) {
        // Frozen clock: don't advance or fire anything while the tab is in the background --
        // just keep the loop alive so it resumes exactly where it left off once visible again.
        rafId = requestAnimationFrame(tick);
        return;
      }

      if (!fired.name && elapsed >= TIMELINE.nameStart) {
        fired.name = true;
        setPhases((p) => ({ ...p, name: true }));
      }
      if (!fired.tag1 && elapsed >= TIMELINE.tag1Start) {
        fired.tag1 = true;
        setPhases((p) => ({ ...p, tag1: true }));
      }
      if (!fired.tag2 && elapsed >= TIMELINE.tag2Start) {
        fired.tag2 = true;
        setPhases((p) => ({ ...p, tag2: true }));
      }
      if (!fired.underline && elapsed >= TIMELINE.underlineStart) {
        fired.underline = true;
        setPhases((p) => ({ ...p, underline: true }));
      }
      if (!fired.fade && elapsed >= TIMELINE.fadeStart) {
        fired.fade = true;
        setPhases((p) => ({ ...p, fading: true }));
      }
      if (!fired.slide && elapsed >= TIMELINE.slideStart) {
        fired.slide = true;
        setPhases((p) => ({ ...p, sliding: true }));
        const remaining = Math.max(0, TIMELINE.slideStart - elapsed);
        slideTimeoutId = window.setTimeout(finish, remaining + TIMELINE.slideDur);
      }

      if (!fired.slide) {
        rafId = requestAnimationFrame(tick);
      }
    }

    rafId = requestAnimationFrame(tick);

    function skip() {
      if (finished || fired.slide) return;
      fired.fade = true;
      fired.slide = true;
      cancelAnimationFrame(rafId);
      setFast(true);
      setPhases((p) => ({ ...p, fading: true }));
      fadeTimeoutId = window.setTimeout(() => {
        setPhases((p) => ({ ...p, sliding: true }));
        slideTimeoutId = window.setTimeout(finish, TIMELINE.skipSlideDur);
      }, TIMELINE.skipFadeDur);
    }

    function handlePointer() {
      skip();
    }
    function handleKey(e: KeyboardEvent) {
      skip();
      void e;
    }

    window.addEventListener('pointerdown', handlePointer);
    window.addEventListener('keydown', handleKey);

    return () => {
      cancelAnimationFrame(rafId);
      window.clearTimeout(fadeTimeoutId);
      window.clearTimeout(slideTimeoutId);
      window.removeEventListener('pointerdown', handlePointer);
      window.removeEventListener('keydown', handleKey);
      document.removeEventListener('visibilitychange', handleVisibility);
      document.body.style.overflow = '';
    };
    // Intentionally runs once: shouldPlay is decided synchronously above and never changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!mounted) return null;

  return (
    <div
      className={[
        'intro-overlay',
        phases.sliding ? (fast ? 'intro-overlay--slide-fast' : 'intro-overlay--slide') : '',
      ].join(' ').trim()}
      aria-hidden="true"
    >
      <div
        className={[
          'intro-group',
          phases.fading ? (fast ? 'intro-group--fade-fast' : 'intro-group--fade') : '',
        ].join(' ').trim()}
      >
        <div className="intro-name" data-show={phases.name}>
          {FULL_NAME}
        </div>
        <div className="intro-tagline">
          <span className="intro-tagline__part1" data-show={phases.tag1}>
            {FULL_TAGLINE_PART1}
          </span>
          <span className="intro-tagline__part2" data-show={phases.tag2}>
            {FULL_TAGLINE_PART2}
          </span>
        </div>
        <div className="intro-underline" data-show={phases.underline} />
      </div>
      <div className="intro-skip">Skip</div>
    </div>
  );
}
