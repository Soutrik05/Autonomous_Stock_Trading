import { useEffect, useRef } from 'react';

/** All tunable numbers in one place. No cursor trail/glow anymore -- the cursor only
 * gently (and smoothly) pushes ambient bubbles out of its way. Ambient drift is ~50%
 * of the previous speed, with an added slow sideways sway and a slow alpha breathe so
 * nothing pops in/out suddenly. Count, sizes, colors and base opacity are unchanged. */
const CONFIG = {
  palette: [
    [79, 143, 224],
    [79, 143, 224],
    [0, 90, 190],
    [0, 63, 136],
    [16, 185, 129],
  ] as Array<[number, number, number]>,
  maxDpr: 2,

  ambientCountDesktop: 22,
  ambientCountTouch: 8,
  ambientRadius: [8, 30] as [number, number],
  ambientAlpha: [0.04, 0.088] as [number, number],
  ambientDrift: [-0.04, 0.04] as [number, number],
  // Gentle sideways sway layered on top of the base drift, like bubbles rising in water.
  swayAmplitude: [4, 10] as [number, number],
  swaySpeed: [0.15, 0.3] as [number, number],
  // Slow opacity "breathe" so a bubble never pops to full/zero alpha abruptly.
  breatheDepth: 0.35,
  breatheSpeed: [0.1, 0.2] as [number, number],

  twinkleCount: 60,
  twinkleRadius: [0.6, 1.6] as [number, number],
  twinkleBaseAlpha: 0.112,
  twinkleAmplitude: 0.128,
  twinkleSpeed: 1.5,

  // Cursor repel: softer force, eased toward/away so bubbles slide, never jump.
  cursorRepelRadius: 170,
  cursorRepelForce: 0.27,
  cursorEaseIn: 0.08,
  cursorEaseOut: 0.04,
};

interface AmbientBubble {
  baseX: number;
  baseY: number;
  r: number;
  alpha: number;
  vx: number;
  vy: number;
  swayAmp: number;
  swaySpeed: number;
  swayPhase: number;
  breatheSpeed: number;
  breathePhase: number;
  pushVx: number;
  pushVy: number;
  color: [number, number, number];
}

interface TwinkleDot {
  x: number;
  y: number;
  r: number;
  phase: number;
  color: [number, number, number];
}

function pickColor(): [number, number, number] {
  return CONFIG.palette[Math.floor(Math.random() * CONFIG.palette.length)];
}

function rand(min: number, max: number): number {
  return min + Math.random() * (max - min);
}

function randIn(range: [number, number]): number {
  return rand(range[0], range[1]);
}

/**
 * Very subtle, themed bubble field, drifting slowly in the background. The cursor only
 * gently and smoothly pushes nearby bubbles out of the way -- no trail, no glow, nothing
 * visibly follows the pointer. Mounted once at the app level (Layout.tsx) so it persists
 * across route changes. Renders nothing under prefers-reduced-motion. No new libraries.
 */
export default function BubbleBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    let reducedMotion = false;
    try {
      reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    } catch {
      // ignore
    }
    if (reducedMotion) return;

    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let isTouch = false;
    try {
      isTouch = window.matchMedia('(pointer: coarse)').matches;
    } catch {
      // ignore
    }

    let width = window.innerWidth;
    let height = window.innerHeight;
    let dpr = Math.min(window.devicePixelRatio || 1, CONFIG.maxDpr);

    function resize() {
      width = window.innerWidth;
      height = window.innerHeight;
      dpr = Math.min(window.devicePixelRatio || 1, CONFIG.maxDpr);
      canvas!.width = Math.round(width * dpr);
      canvas!.height = Math.round(height * dpr);
      canvas!.style.width = `${width}px`;
      canvas!.style.height = `${height}px`;
      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    resize();
    window.addEventListener('resize', resize);

    const ambientCount = isTouch ? CONFIG.ambientCountTouch : CONFIG.ambientCountDesktop;
    const ambient: AmbientBubble[] = Array.from({ length: ambientCount }, () => ({
      baseX: Math.random() * width,
      baseY: Math.random() * height,
      r: randIn(CONFIG.ambientRadius),
      alpha: randIn(CONFIG.ambientAlpha),
      vx: randIn(CONFIG.ambientDrift),
      vy: randIn(CONFIG.ambientDrift),
      swayAmp: randIn(CONFIG.swayAmplitude),
      swaySpeed: randIn(CONFIG.swaySpeed),
      swayPhase: Math.random() * Math.PI * 2,
      breatheSpeed: randIn(CONFIG.breatheSpeed),
      breathePhase: Math.random() * Math.PI * 2,
      pushVx: 0,
      pushVy: 0,
      color: pickColor(),
    }));

    const twinkles: TwinkleDot[] = Array.from({ length: CONFIG.twinkleCount }, () => ({
      x: Math.random() * width,
      y: Math.random() * height,
      r: randIn(CONFIG.twinkleRadius),
      phase: Math.random() * Math.PI * 2,
      color: pickColor(),
    }));

    const mouse = { x: -9999, y: -9999, active: false };

    function handleMouseMove(e: MouseEvent) {
      mouse.x = e.clientX;
      mouse.y = e.clientY;
      mouse.active = true;
    }

    function handleMouseLeave() {
      mouse.active = false;
    }

    if (!isTouch) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseleave', handleMouseLeave);
    }

    let paused = document.hidden;
    function handleVisibility() {
      paused = document.hidden;
    }
    document.addEventListener('visibilitychange', handleVisibility);

    let rafId = 0;
    let t = 0;

    function drawBubble(x: number, y: number, r: number, alpha: number, color: [number, number, number]) {
      const [cr, cg, cb] = color;
      const gradient = ctx!.createRadialGradient(x, y, 0, x, y, r);
      gradient.addColorStop(0, `rgba(${cr}, ${cg}, ${cb}, ${alpha})`);
      gradient.addColorStop(1, `rgba(${cr}, ${cg}, ${cb}, 0)`);
      ctx!.fillStyle = gradient;
      ctx!.beginPath();
      ctx!.arc(x, y, r, 0, Math.PI * 2);
      ctx!.fill();
    }

    function tick() {
      rafId = requestAnimationFrame(tick);
      if (paused) return;
      t += 0.016;
      ctx!.clearRect(0, 0, width, height);

      // Ambient bubbles: slow drift + sideways sway + slow alpha breathe, softly and
      // smoothly pushed away from the cursor (never a sudden jump either way).
      for (const b of ambient) {
        b.baseX += b.vx;
        b.baseY += b.vy;
        if (b.baseX < -40) b.baseX = width + 40;
        if (b.baseX > width + 40) b.baseX = -40;
        if (b.baseY < -40) b.baseY = height + 40;
        if (b.baseY > height + 40) b.baseY = -40;

        const swayX = Math.sin(t * b.swaySpeed + b.swayPhase) * b.swayAmp;
        const x = b.baseX + swayX;
        const y = b.baseY;

        if (!isTouch && mouse.active) {
          const dx = x - mouse.x;
          const dy = y - mouse.y;
          const d = Math.hypot(dx, dy);
          if (d < CONFIG.cursorRepelRadius && d > 0.001) {
            const force = CONFIG.cursorRepelForce * Math.pow(1 - d / CONFIG.cursorRepelRadius, 2);
            const targetVx = (dx / d) * force;
            const targetVy = (dy / d) * force;
            b.pushVx += (targetVx - b.pushVx) * CONFIG.cursorEaseIn;
            b.pushVy += (targetVy - b.pushVy) * CONFIG.cursorEaseIn;
          } else {
            b.pushVx += (0 - b.pushVx) * CONFIG.cursorEaseOut;
            b.pushVy += (0 - b.pushVy) * CONFIG.cursorEaseOut;
          }
        } else {
          b.pushVx += (0 - b.pushVx) * CONFIG.cursorEaseOut;
          b.pushVy += (0 - b.pushVy) * CONFIG.cursorEaseOut;
        }

        b.baseX += b.pushVx;
        b.baseY += b.pushVy;

        const breathe = 1 - CONFIG.breatheDepth * (0.5 + 0.5 * Math.sin(t * b.breatheSpeed + b.breathePhase));
        drawBubble(x + b.pushVx, y + b.pushVy, b.r, Math.max(0, b.alpha * breathe), b.color);
      }

      // Twinkling dots.
      for (const dot of twinkles) {
        const alpha = Math.max(0, CONFIG.twinkleBaseAlpha + CONFIG.twinkleAmplitude * Math.sin(t * CONFIG.twinkleSpeed + dot.phase));
        drawBubble(dot.x, dot.y, dot.r, alpha, dot.color);
      }
    }

    rafId = requestAnimationFrame(tick);

    return () => {
      cancelAnimationFrame(rafId);
      window.removeEventListener('resize', resize);
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseleave', handleMouseLeave);
      document.removeEventListener('visibilitychange', handleVisibility);
    };
  }, []);

  let prefersReducedMotion = false;
  try {
    prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  } catch {
    // ignore
  }
  if (prefersReducedMotion) return null;

  return <canvas ref={canvasRef} className="bubble-background" aria-hidden="true" />;
}
