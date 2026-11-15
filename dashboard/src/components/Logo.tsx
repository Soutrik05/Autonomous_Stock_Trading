import { useRef, type CSSProperties, type MouseEvent } from 'react';
import { Link } from 'react-router-dom';

type LogoSize = 'header';

const NAME_SIZE: Record<LogoSize, string> = {
  header: '30px',
};

/**
 * Brand wordmark: "StockMinds" (Playfair Display 900) over a "five minds, one
 * market" tagline (Great Vibes). A green cursor-tracked spotlight sweeps the
 * name on hover via a ::after pseudo-element clipped to the same text, driven
 * by --mx/--my (px, relative to the link) updated through requestAnimationFrame.
 */
export default function Logo({ size = 'header', className = '' }: { size?: LogoSize; className?: string }) {
  const linkRef = useRef<HTMLAnchorElement>(null);
  const rafRef = useRef<number | null>(null);

  const handleMouseMove = (e: MouseEvent<HTMLAnchorElement>) => {
    const box = linkRef.current;
    if (!box) return;
    const rect = box.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    rafRef.current = requestAnimationFrame(() => {
      box.style.setProperty('--mx', `${mx}px`);
      box.style.setProperty('--my', `${my}px`);
    });
  };

  return (
    <Link
      ref={linkRef}
      to="/"
      aria-label="StockMinds home"
      className={`logo logo--${size} ${className}`}
      onMouseMove={handleMouseMove}
      style={{ '--fs': NAME_SIZE[size] } as CSSProperties}
    >
      <span className="logo__name" data-text="StockMinds">
        StockMinds
      </span>
      <span className="logo__tagline">five minds, one market</span>
    </Link>
  );
}
