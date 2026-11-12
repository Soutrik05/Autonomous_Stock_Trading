import { useState, useEffect } from 'react';
import { NavLink, Link } from 'react-router-dom';
import {
  Menu,
  X,
  Activity,
} from 'lucide-react';
import { getIsMockMode, setMockMode, apiService } from '../services/api';
import SystemHealthDrawer from './SystemHealthDrawer';

export default function Header() {
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
  const [isBackendHealthy, setIsBackendHealthy] = useState<boolean | null>(null);

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

  // Check backend health periodically
  useEffect(() => {
    const checkConn = async () => {
      const healthy = await apiService.checkBackendConnection();
      setIsBackendHealthy(healthy);
    };
    checkConn();
    const interval = setInterval(checkConn, 15000);
    return () => clearInterval(interval);
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
    { to: '/portfolio/simons', label: 'Portfolio' },
    { to: '/comparison', label: 'Comparison' },
    { to: '/backtest', label: 'Backtest' },
    { to: '/pulse', label: 'Pulse' },
  ];

  return (
    <>
      <header className="sticky top-0 z-40 bg-[#141414]/95 backdrop-blur-md border-b border-white/[0.08] transition-colors">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-14">
            
            {/* Left: Clean Brand Mark */}
            <div className="flex items-center">
              <Link to="/" className="flex items-center group">
                <span className="text-xl sm:text-2xl font-display font-medium tracking-tight text-white group-hover:text-[#D4AF37] transition-colors">
                  StockMinds
                </span>
              </Link>
            </div>

            {/* Center: Clean, Spaced, Centered Navigation */}
            <nav className="hidden md:flex items-center gap-7 lg:gap-9 font-mono text-[13px]">
              {navItems.map(({ to, label, end }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={end}
                  className={({ isActive }) =>
                    `transition-colors relative py-1.5 ${
                      isActive
                        ? 'text-[#D4AF37] font-medium'
                        : 'text-zinc-400 hover:text-white'
                    }`
                  }
                >
                  {({ isActive }) => (
                    <>
                      <span>{label}</span>
                      {isActive && (
                        <span className="absolute -bottom-1 left-0 right-0 h-[2px] bg-[#D4AF37]" />
                      )}
                    </>
                  )}
                </NavLink>
              ))}
            </nav>

            {/* Right: Telemetry & Controls (Right-Aligned) */}
            <div className="hidden sm:flex items-center gap-3 font-mono text-xs">
              <div className="flex items-center gap-2 px-2.5 py-1 rounded border border-white/[0.08] bg-[#161616] text-[11px] text-zinc-300">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                <span className="font-medium text-white">{displayDate}</span>
              </div>
              <span className="text-zinc-500 text-xs tabular-nums">
                {istTime || '15:30:00 IST'}
              </span>

              {/* Drawer Health Trigger with quiet status dot */}
              <button
                onClick={() => setIsHealthOpen(true)}
                className="flex items-center gap-2 px-2.5 py-1 rounded border border-white/[0.08] hover:border-white/20 text-zinc-400 hover:text-white transition-colors cursor-pointer text-[11px]"
                title="System Telemetry, Pipelines & API Settings"
              >
                <span
                  className={`w-1.5 h-1.5 rounded-full ${
                    isBackendHealthy ? 'bg-emerald-400' : 'bg-zinc-500'
                  }`}
                />
                <Activity className="w-3.5 h-3.5 text-zinc-400" />
              </button>
            </div>

            {/* Mobile Menu Button */}
            <div className="md:hidden flex items-center gap-2">
              <button
                onClick={() => setIsHealthOpen(true)}
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
                    `block px-3 py-2 rounded text-sm font-mono ${
                      isActive
                        ? 'bg-white/[0.08] text-[#D4AF37] font-semibold'
                        : 'text-zinc-400 hover:text-white hover:bg-white/[0.04]'
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
