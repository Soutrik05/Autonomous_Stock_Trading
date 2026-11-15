import { useEffect, useRef } from 'react';

/** All tunable numbers in one place. Colors/sizes/repel/decay are unchanged from the
 * first version; the alpha/count values here are ~1.5x the original, still subtle. */
const CONFIG = {
  palette: [
    [79, 143, 224],
    [79, 143, 224],
    [0, 90, 190],
    [0, 63, 136],
    [16, 185, 129],
  ] as Array<[number, number, number]>,
  maxDpr: 2,
  cursorRepelRadius: 170,
  cursorRepelForce: 0.45,

  ambientCountDesktop: 22,
  ambientCountTouch: 8,
  ambientRadius: [8, 30] as [number, number],
  ambientAlpha: [0.05, 0.11] as [number, number],
  ambientDrift: [-0.08, 0.08] as [number, number],

  twinkleCount: 60,
  twinkleRadius: [0.6, 1.6] as [number, number],
  twinkleBaseAlpha: 0.14,
  twinkleAmplitude: 0.16,
  twinkleSpeed: 1.5,

  trailSpawnDistance: 16,
  trailMaxPerMove: 2,
  trailRadius: [2.5, 9] as [number, number],
  trailVy: [-0.6, -0.2] as [number, number],
  trailDecay: [0.022, 0.034] as [number, number],
  trailAlphaScale: 0.3,
  trailRingMinRadius: 5,

  cursorGlowRadius: 60,
  cursorGlowAlpha: 0.1,
  cursorGlowColor: [0, 63, 136] as [number, number, number],
};

interface AmbientBubble {
  x: number;
  y: number;
  r: number;
  alpha: number;
  vx: number;
  vy: number;
  color: [number, number, number];
}

interface TwinkleDot {
  x: number;
  y: number;
  r: number;
  phase: number;
  color: [number, number, number];
}

interface TrailBubble {
  x: number;
  y: number;
  r: number;
  vy: number;
  life: number;
  decay: number;
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
 * Very subtle, themed, cursor-reactive bubble field rendered behind page content.
 * Mounted once at the app level (Layout.tsx) so it persists across route changes.
 * Renders nothing at all under prefers-reduced-motion. Pure canvas, no new libraries.
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
      x: Math.random() * width,
      y: Math.random() * height,
      r: randIn(CONFIG.ambientRadius),
      alpha: randIn(CONFIG.ambientAlpha),
      vx: randIn(CONFIG.ambientDrift),
      vy: randIn(CONFIG.ambientDrift),
      color: pickColor(),
    }));

    const twinkles: TwinkleDot[] = Array.from({ length: CONFIG.twinkleCount }, () => ({
      x: Math.random() * width,
      y: Math.random() * height,
      r: randIn(CONFIG.twinkleRadius),
      phase: Math.random() * Math.PI * 2,
      color: pickColor(),
    }));

    let trail: TrailBubble[] = [];
    const mouse = { x: -9999, y: -9999, active: false };
    let lastSpawn = { x: -9999, y: -9999 };

    function handleMouseMove(e: MouseEvent) {
      mouse.x = e.clientX;
      mouse.y = e.clientY;
      mouse.active = true;
      if (isTouch) return;

      const dx = mouse.x - lastSpawn.x;
      const dy = mouse.y - lastSpawn.y;
      if (Math.hypot(dx, dy) < CONFIG.trailSpawnDistance) return;
      lastSpawn = { x: mouse.x, y: mouse.y };

      const spawnCount = Math.min(CONFIG.trailMaxPerMove, 1 + Math.floor(Math.random() * 2));
      for (let i = 0; i < spawnCount; i++) {
        trail.push({
          x: mouse.x + rand(-4, 4),
          y: mouse.y + rand(-4, 4),
          r: randIn(CONFIG.trailRadius),
          vy: randIn(CONFIG.trailVy),
          life: 1,
          decay: randIn(CONFIG.trailDecay),
          color: pickColor(),
        });
      }
    }

    function handleMouseLeave() {
      mouse.active = false;
      trail = [];
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

      // Ambient bubbles: slow drift, gently repelled by the cursor.
      for (const b of ambient) {
        b.x += b.vx;
        b.y += b.vy;
        if (b.x < -40) b.x = width + 40;
        if (b.x > width + 40) b.x = -40;
        if (b.y < -40) b.y = height + 40;
        if (b.y > height + 40) b.y = -40;

        if (!isTouch && mouse.active) {
          const dx = b.x - mouse.x;
          const dy = b.y - mouse.y;
          const d = Math.hypot(dx, dy);
          if (d < CONFIG.cursorRepelRadius && d > 0.001) {
            const force = CONFIG.cursorRepelForce * Math.pow(1 - d / CONFIG.cursorRepelRadius, 2);
            b.x += (dx / d) * force;
            b.y += (dy / d) * force;
          }
        }

        drawBubble(b.x, b.y, b.r, b.alpha, b.color);
      }

      // Twinkling dots.
      for (const dot of twinkles) {
        const alpha = Math.max(0, CONFIG.twinkleBaseAlpha + CONFIG.twinkleAmplitude * Math.sin(t * CONFIG.twinkleSpeed + dot.phase));
        drawBubble(dot.x, dot.y, dot.r, alpha, dot.color);
      }

      // Faint glow under the cursor.
      if (!isTouch && mouse.active) {
        drawBubble(mouse.x, mouse.y, CONFIG.cursorGlowRadius, CONFIG.cursorGlowAlpha, CONFIG.cursorGlowColor);
      }

      // Cursor trail: rise, fade, thin ring once big enough.
      if (trail.length > 0) {
        trail = trail.filter((p) => p.life > 0);
        for (const p of trail) {
          p.y += p.vy;
          p.life -= p.decay;
          const alpha = Math.max(0, CONFIG.trailAlphaScale * p.life);
          drawBubble(p.x, p.y, p.r, alpha, p.color);
          if (p.r > CONFIG.trailRingMinRadius) {
            const [cr, cg, cb] = p.color;
            ctx!.strokeStyle = `rgba(${cr}, ${cg}, ${cb}, ${alpha * 0.6})`;
            ctx!.lineWidth = 0.75;
            ctx!.beginPath();
            ctx!.arc(p.x, p.y, p.r, 0, Math.PI * 2);
            ctx!.stroke();
          }
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
