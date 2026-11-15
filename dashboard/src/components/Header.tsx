import { useState, useEffect, useRef } from 'react';
import { NavLink } from 'react-router-dom';
import {
  Menu,
  X,
  Activity,
} from 'lucide-react';
import { getIsMockMode, setMockMode } from '../services/api';
import { useMarketOpen } from '../utils/marketHours';
import SystemHealthDrawer from './SystemHealthDrawer';
import Logo from './Logo';

const MARKET_STATUS_LABEL = {
  open: 'Market open (NSE, 9:15-15:30 IST)',
  closed: 'Market closed',
};

const SCROLL_FROST_THRESHOLD = 10;
const SCROLL_HIDE_THRESHOLD = 90;
const SCROLL_JITTER_THRESHOLD = 4;

interface HeaderProps {
  onHeightChange?: (height: number) => void;
}

export default function Header({ onHeightChange }: HeaderProps) {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isHealthOpen, setIsHealthOpen] = useState(false);
  const [isMock, setIsMock] = useState(getIsMockMode());
  const [istTime, setIstTime] = useState('');
  const [displayDate, setDisplayDate] = useState(() => {
    return new Date().toLocaleDateString('en-IN', {
      timeZone: 'Asia/Kolkata',
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    });
  });
  const isMarketOpen = useMarketOpen();
  const marketStatusLabel = isMarketOpen ? MARKET_STATUS_LABEL.open : MARKET_STATUS_LABEL.closed;

  const headerRef = useRef<HTMLElement>(null);
  const [isScrolled, setIsScrolled] = useState(false);
  const [isHidden, setIsHidden] = useState(false);
  const [isHeaderHovered, setIsHeaderHovered] = useState(false);
  const [isNavFocused, setIsNavFocused] = useState(false);

  // The header must never hide while a nav item has keyboard focus, the health drawer
  // is open, or the mouse is over it. Each action that pins it also reveals it right
  // away (handled at the call sites below, not here, to avoid setState-in-effect).
  const pinnedRef = useRef(false);
  useEffect(() => {
    pinnedRef.current = isHealthOpen || isHeaderHovered || isNavFocused;
  }, [isHealthOpen, isHeaderHovered, isNavFocused]);

  // Report the header's own rendered height so the page content can pad itself clear
  // of the now `position: fixed` header (it otherwise grows, e.g. the mobile dropdown).
  useEffect(() => {
    const el = headerRef.current;
    if (!el || !onHeightChange) return;
    const report = () => onHeightChange(el.offsetHeight);
    report();
    const observer = new ResizeObserver(report);
    observer.observe(el);
    return () => observer.disconnect();
  }, [onHeightChange]);

  // Single passive scroll listener, coalesced through requestAnimationFrame, ignoring
  // sub-4px jitter so trackpad/momentum noise doesn't flicker the hide/show state.
  useEffect(() => {
    let lastY = window.scrollY;
    let ticking = false;

    const update = () => {
      ticking = false;
      const currentY = window.scrollY;
      setIsScrolled(currentY > SCROLL_FROST_THRESHOLD);

      const delta = currentY - lastY;
      if (Math.abs(delta) < SCROLL_JITTER_THRESHOLD) return;

      if (delta > 0 && currentY > SCROLL_HIDE_THRESHOLD && !pinnedRef.current) {
        setIsHidden(true);
      } else if (delta < 0) {
        setIsHidden(false);
      }
      lastY = currentY;
    };

    const handleScroll = () => {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(update);
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  // Update IST clock and date dynamically
  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setIstTime(
        now.toLocaleTimeString('en-IN', {
          timeZone: 'Asia/Kolkata',
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          hour12: false,
        }) + ' IST'
      );
      setDisplayDate(
        now.toLocaleDateString('en-IN', {
          timeZone: 'Asia/Kolkata',
          day: 'numeric',
          month: 'short',
          year: 'numeric',
        })
      );
    };
    updateTime();
    const timer = setInterval(updateTime, 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    const handleSync = () => setIsMock(getIsMockMode());
    window.addEventListener('mock_mode_changed', handleSync);
    return () => window.removeEventListener('mock_mode_changed', handleSync);
  }, []);

  const handleToggleMock = () => {
    const next = !isMock;
    setIsMock(next);
    setMockMode(next);
  };

  const navItems = [
    { to: '/', label: 'Overview', end: true },
    { to: '/leaderboard', label: 'Leaderboard' },
    { to: '/portfolio/simons', label: 'Agents Terminal' },
    { to: '/comparison', label: 'Comparison' },
    { to: '/backtest', label: 'Backtest' },
    { to: '/pulse', label: 'Pulse' },
  ];

  return (
    <>
      <header
        ref={headerRef}
        className={`site-header ${isScrolled ? 'site-header--scrolled' : ''} ${isHidden ? 'site-header--hidden' : ''}`}
        onMouseEnter={() => {
          setIsHeaderHovered(true);
          setIsHidden(false);
        }}
        onMouseLeave={() => setIsHeaderHovered(false)}
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center min-h-14 py-1.5">

            {/* Left: Clean Brand Mark */}
            <div className="flex items-center flex-shrink-0">
              <Logo size="header" />
            </div>

            {/* Center: Clean, Spaced, Centered Navigation */}
            <nav
              className="hidden md:flex items-center gap-7 lg:gap-9 font-mono text-[13px] ml-10 flex-shrink-0"
              onFocus={() => {
                setIsNavFocused(true);
                setIsHidden(false);
              }}
              onBlur={(e) => {
                if (!e.currentTarget.contains(e.relatedTarget as Node | null)) {
                  setIsNavFocused(false);
                }
              }}
            >
              {navItems.map(({ to, label, end }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={end}
                  className={({ isActive }) =>
                    `nav-link whitespace-nowrap flex-shrink-0 transition-colors duration-[250ms] relative py-1.5 ${
                      isActive
                        ? 'is-active text-brand-blue-text font-medium'
                        : 'text-zinc-400 hover:text-brand-blue-text focus-visible:text-brand-blue-text'
                    }`
                  }
                >
                  {label}
                </NavLink>
              ))}
            </nav>

            {/* Right: Telemetry & Controls (Right-Aligned) */}
            <div className="hidden sm:flex items-center gap-3 font-mono text-xs flex-shrink-0">
              <div className="flex items-center gap-2 px-2.5 py-1 rounded border border-white/[0.08] bg-[#161616] text-[11px] text-zinc-300 whitespace-nowrap flex-shrink-0">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse flex-shrink-0" />
                <span className="font-medium text-white hidden min-[1100px]:inline">{displayDate}</span>
              </div>
              <span
                className={`hidden min-[1280px]:inline text-xs tabular-nums whitespace-nowrap flex-shrink-0 transition-colors duration-150 ${
                  isMarketOpen ? 'text-brand-blue-text' : 'text-zinc-500'
                }`}
                title={marketStatusLabel}
                aria-label={marketStatusLabel}
              >
                {istTime || '15:30:00 IST'}
              </span>

              {/* Drawer Health Trigger with market-state pulse dot */}
              <button
                onClick={() => {
                  setIsHealthOpen(true);
                  setIsHidden(false);
                }}
                className="flex items-center gap-2 px-2.5 py-1 rounded border border-white/[0.08] hover:border-white/20 text-zinc-400 hover:text-white transition-colors cursor-pointer text-[11px] flex-shrink-0"
                title={marketStatusLabel}
                aria-label={marketStatusLabel}
              >
                <span className="relative flex items-center justify-center w-1.5 h-1.5">
                  {isMarketOpen && (
                    <span className="absolute inline-flex h-full w-full rounded-full bg-brand-blue opacity-75 motion-safe:animate-ping" />
                  )}
                  <span
                    className={`relative inline-flex w-1.5 h-1.5 rounded-full ${
                      isMarketOpen ? 'bg-brand-blue-text' : 'bg-zinc-500'
                    }`}
                  />
                </span>
                <Activity
                  className={`w-3.5 h-3.5 transition-colors duration-150 ${
                    isMarketOpen ? 'text-brand-blue-text' : 'text-zinc-400'
                  }`}
                />
              </button>
            </div>

            {/* Mobile Menu Button */}
            <div className="md:hidden flex items-center gap-2">
              <button
                onClick={() => {
                  setIsHealthOpen(true);
                  setIsHidden(false);
                }}
                className="p-1.5 text-zinc-400"
                title="System Health"
              >
                <Activity className="w-4 h-4" />
              </button>
              <button
                onClick={() => setIsMenuOpen(!isMenuOpen)}
                className="p-1.5 rounded text-zinc-400 hover:text-white"
              >
                {isMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
              </button>
            </div>
          </div>

          {/* Mobile Nav Dropdown */}
          {isMenuOpen && (
            <div className="md:hidden py-3 border-t border-white/10 space-y-1">
              {navItems.map(({ to, label, end }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={end}
                  onClick={() => setIsMenuOpen(false)}
                  className={({ isActive }) =>
                    `block px-3 py-2 rounded text-sm font-mono transition-colors duration-150 ${
                      isActive
                        ? 'bg-brand-blue-soft text-brand-blue-text font-semibold'
                        : 'text-zinc-400 hover:text-brand-blue-text hover:bg-white/[0.04]'
                    }`
                  }
                >
                  {label}
                </NavLink>
              ))}

              <div className="pt-2 border-t border-white/10 flex justify-between items-center text-xs px-2 font-mono">
                <span className="text-zinc-400">{istTime}</span>
                <button
                  onClick={handleToggleMock}
                  className="px-2.5 py-1 rounded bg-white/[0.05] text-zinc-300 border border-white/10 text-[11px]"
                >
                  {isMock ? 'Mock Mode' : 'Live API'}
                </button>
              </div>
            </div>
          )}
        </div>
      </header>

      {/* Slide-Over System Health Drawer */}
      <SystemHealthDrawer isOpen={isHealthOpen} onClose={() => setIsHealthOpen(false)} />
    </>
  );
}
