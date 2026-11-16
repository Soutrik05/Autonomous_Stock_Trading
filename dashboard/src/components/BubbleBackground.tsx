import { useEffect, useRef } from 'react';

/** All tunable numbers in one place. Delta-time driven (frame-rate independent), capped
 * at CONFIG.maxDeltaTime so a backgrounded tab never makes bubbles jump on return. No
 * cursor trail/rings/spawned bubbles -- the cursor only (a) drags one soft two-tone glow
 * a little behind it, and (b) gently, smoothly pushes nearby ambient bubbles aside. */
const CONFIG = {
  palette: [
    [79, 143, 224],
    [79, 143, 224],
    [0, 90, 190],
    [0, 63, 136],
    [16, 185, 129],
  ] as Array<[number, number, number]>,
  maxDpr: 2,
  maxDeltaTime: 0.05, // seconds; clamps the dt used for all motion below

  ambientCountDesktop: 35,
  ambientCountTouch: 14,
  // Radius is biased toward the low end of this range; only occasionally reaches the
  // top, for a few slightly-larger bubbles that read as background depth.
  ambientRadiusMin: 8,
  ambientRadiusMax: 38,
  ambientRadiusBias: 2.2,
  ambientAlpha: [0.056, 0.1232] as [number, number],
  // px/second. Each bubble picks its own speed and its own direction (mostly upward,
  // with a spread so they don't all drift the same way) -- see ambientAngleSpreadDeg.
  ambientSpeed: [12, 25] as [number, number],
  ambientAngleSpreadDeg: 35,
  // Gentle sideways sway layered on top of the base drift, like bubbles rising in water.
  swayAmplitude: [15, 30] as [number, number],
  swayPeriod: [6, 10] as [number, number], // seconds per full left-right cycle
  // Slow opacity "breathe" so a bubble never sits at a flat, static brightness.
  breatheDepth: 0.35,
  breatheSpeed: [0.1, 0.2] as [number, number],
  // When a bubble wraps to the opposite edge, it fades back in over this many seconds
  // instead of popping to full opacity immediately.
  wrapFadeInSeconds: 1.4,

  twinkleCount: 78,
  twinkleRadius: [0.6, 1.6] as [number, number],
  twinkleBaseAlpha: 0.1456,
  twinkleAmplitude: 0.1664,
  twinkleSpeed: 1.5,

  // Cursor repel on ambient bubbles: soft force, eased so bubbles slide, never jump.
  cursorRepelRadius: 170,
  cursorRepelForce: 0.27,
  cursorEaseInRate: 4.8, // per second
  cursorEaseOutRate: 2.4, // per second

  // Cursor glow: one soft green glow (plus a fainter, larger blue one behind it) that
  // lags the cursor and fades in/out as the pointer enters/leaves the window.
  glowGreenColor: [16, 185, 129] as [number, number, number],
  glowGreenRadius: 220,
  glowGreenAlpha: 0.065,
  glowBlueColor: [0, 63, 136] as [number, number, number],
  glowBlueRadius: 260,
  glowBlueAlpha: 0.039,
  glowFollowRate: 5.5, // per second; ~9% of the remaining distance per 60fps frame
  glowFadeRate: 3, // per second
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
  wrapFadeTimer: number;
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

function randomRadius(): number {
  const biased = Math.pow(Math.random(), CONFIG.ambientRadiusBias);
  return CONFIG.ambientRadiusMin + biased * (CONFIG.ambientRadiusMax - CONFIG.ambientRadiusMin);
}

function createAmbientBubble(x: number, y: number): AmbientBubble {
  const speed = randIn(CONFIG.ambientSpeed);
  // Mostly straight up (-90deg), with a spread so bubbles don't all move identically.
  const angleDeg = -90 + rand(-CONFIG.ambientAngleSpreadDeg, CONFIG.ambientAngleSpreadDeg);
  const angle = (angleDeg * Math.PI) / 180;
  return {
    baseX: x,
    baseY: y,
    r: randomRadius(),
    alpha: randIn(CONFIG.ambientAlpha),
    vx: Math.cos(angle) * speed,
    vy: Math.sin(angle) * speed,
    swayAmp: randIn(CONFIG.swayAmplitude),
    swaySpeed: (2 * Math.PI) / randIn(CONFIG.swayPeriod),
    swayPhase: rand(0, Math.PI * 2),
    breatheSpeed: randIn(CONFIG.breatheSpeed),
    breathePhase: rand(0, Math.PI * 2),
    pushVx: 0,
    pushVy: 0,
    wrapFadeTimer: 0,
    color: pickColor(),
  };
}

/** Evenly spreads `count` starting points across the whole width/height (a jittered
 * grid) instead of pure random placement, which tends to look clustered in places. */
function evenlySpreadPoints(count: number, width: number, height: number): Array<[number, number]> {
  const aspect = width / height || 1;
  const cols = Math.max(1, Math.round(Math.sqrt(count * aspect)));
  const rows = Math.max(1, Math.ceil(count / cols));
  const cellW = width / cols;
  const cellH = height / rows;
  const points: Array<[number, number]> = [];
  for (let i = 0; i < count; i++) {
    const col = i % cols;
    const row = Math.floor(i / cols);
    const x = col * cellW + rand(cellW * 0.15, cellW * 0.85);
    const y = row * cellH + rand(cellH * 0.15, cellH * 0.85);
    points.push([x, y]);
  }
  return points;
}

/**
 * Very subtle, themed bubble field, drifting slowly in the background, plus one soft
 * two-tone glow that lags the cursor. No trail, no rings, no spawned bubbles -- the
 * cursor only gently and smoothly pushes nearby ambient bubbles out of its way. Mounted
 * once at the app level (Layout.tsx) so it persists across route changes. Renders
 * nothing under prefers-reduced-motion. No new libraries.
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
    const startPoints = evenlySpreadPoints(ambientCount, width, height);
    const ambient: AmbientBubble[] = startPoints.map(([x, y]) => createAmbientBubble(x, y));

    const twinkles: TwinkleDot[] = Array.from({ length: CONFIG.twinkleCount }, () => ({
      x: Math.random() * width,
      y: Math.random() * height,
      r: randIn(CONFIG.twinkleRadius),
      phase: Math.random() * Math.PI * 2,
      color: pickColor(),
    }));

    const mouse = { x: -9999, y: -9999, active: false };
    const glow = { x: 0, y: 0, opacity: 0, initialized: false };

    function handleMouseMove(e: MouseEvent) {
      mouse.x = e.clientX;
      mouse.y = e.clientY;
      mouse.active = true;
      if (!glow.initialized) {
        glow.x = e.clientX;
        glow.y = e.clientY;
        glow.initialized = true;
      }
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
    let lastTime: number | null = null;

    function drawGlow(x: number, y: number, r: number, alpha: number, color: [number, number, number]) {
      if (alpha <= 0.001) return;
      const [cr, cg, cb] = color;
      const gradient = ctx!.createRadialGradient(x, y, 0, x, y, r);
      gradient.addColorStop(0, `rgba(${cr}, ${cg}, ${cb}, ${alpha})`);
      gradient.addColorStop(1, `rgba(${cr}, ${cg}, ${cb}, 0)`);
      ctx!.fillStyle = gradient;
      ctx!.beginPath();
      ctx!.arc(x, y, r, 0, Math.PI * 2);
      ctx!.fill();
    }

    function tick(now: number) {
      rafId = requestAnimationFrame(tick);
      if (paused) return;
      if (lastTime === null) lastTime = now;
      let dt = (now - lastTime) / 1000;
      lastTime = now;
      dt = Math.min(dt, CONFIG.maxDeltaTime);
      t += dt;
      ctx!.clearRect(0, 0, width, height);

      const easeInFactor = Math.min(1, CONFIG.cursorEaseInRate * dt);
      const easeOutFactor = Math.min(1, CONFIG.cursorEaseOutRate * dt);

      // Ambient bubbles: slow upward drift + sideways sway + slow alpha breathe,
      // softly and smoothly pushed away from the cursor (never a sudden jump either
      // way), and fading back in (not popping) after wrapping to the opposite edge.
      for (const b of ambient) {
        b.baseX += b.vx * dt;
        b.baseY += b.vy * dt;

        if (b.baseX < -60) {
          b.baseX = width + 60;
          b.wrapFadeTimer = CONFIG.wrapFadeInSeconds;
        } else if (b.baseX > width + 60) {
          b.baseX = -60;
          b.wrapFadeTimer = CONFIG.wrapFadeInSeconds;
        }
        if (b.baseY < -60) {
          b.baseY = height + 60;
          b.wrapFadeTimer = CONFIG.wrapFadeInSeconds;
        } else if (b.baseY > height + 60) {
          b.baseY = -60;
          b.wrapFadeTimer = CONFIG.wrapFadeInSeconds;
        }

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
            b.pushVx += (targetVx - b.pushVx) * easeInFactor;
            b.pushVy += (targetVy - b.pushVy) * easeInFactor;
          } else {
            b.pushVx += (0 - b.pushVx) * easeOutFactor;
            b.pushVy += (0 - b.pushVy) * easeOutFactor;
          }
        } else {
          b.pushVx += (0 - b.pushVx) * easeOutFactor;
          b.pushVy += (0 - b.pushVy) * easeOutFactor;
        }

        b.baseX += b.pushVx;
        b.baseY += b.pushVy;

        if (b.wrapFadeTimer > 0) b.wrapFadeTimer = Math.max(0, b.wrapFadeTimer - dt);
        const wrapFadeMul = 1 - b.wrapFadeTimer / CONFIG.wrapFadeInSeconds;

        const breathe = 1 - CONFIG.breatheDepth * (0.5 + 0.5 * Math.sin(t * b.breatheSpeed + b.breathePhase));
        drawGlow(x + b.pushVx, y + b.pushVy, b.r, Math.max(0, b.alpha * breathe * wrapFadeMul), b.color);
      }

      // Twinkling dots.
      for (const dot of twinkles) {
        const alpha = Math.max(0, CONFIG.twinkleBaseAlpha + CONFIG.twinkleAmplitude * Math.sin(t * CONFIG.twinkleSpeed + dot.phase));
        drawGlow(dot.x, dot.y, dot.r, alpha, dot.color);
      }

      // Soft two-tone glow that lags the cursor and fades in/out with it.
      if (!isTouch) {
        const followFactor = Math.min(1, CONFIG.glowFollowRate * dt);
        glow.x += (mouse.x - glow.x) * followFactor;
        glow.y += (mouse.y - glow.y) * followFactor;

        const targetOpacity = mouse.active ? 1 : 0;
        const fadeFactor = Math.min(1, CONFIG.glowFadeRate * dt);
        glow.opacity += (targetOpacity - glow.opacity) * fadeFactor;

        if (glow.opacity > 0.001) {
          const prevComposite = ctx!.globalCompositeOperation;
          ctx!.globalCompositeOperation = 'lighter';
          drawGlow(glow.x, glow.y, CONFIG.glowBlueRadius, CONFIG.glowBlueAlpha * glow.opacity, CONFIG.glowBlueColor);
          drawGlow(glow.x, glow.y, CONFIG.glowGreenRadius, CONFIG.glowGreenAlpha * glow.opacity, CONFIG.glowGreenColor);
          ctx!.globalCompositeOperation = prevComposite;
        }
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
