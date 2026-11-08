import { useState, useEffect } from 'react';
import { NavLink, Link } from 'react-router-dom';
import {
  Menu,
  X,
} from 'lucide-react';
import { getIsMockMode, setMockMode, apiService } from '../services/api';
import SystemHealthDrawer from './SystemHealthDrawer';

export default function Header() {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isHealthOpen, setIsHealthOpen] = useState(false);
  const [isMock, setIsMock] = useState(getIsMockMode());
  const [istTime, setIstTime] = useState('');
  const [isBackendHealthy, setIsBackendHealthy] = useState<boolean | null>(null);

  // Update IST clock every second
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
    { to: '/backtest', label: 'Backtest', badge: 'Week 4' },
    { to: '/pulse', label: 'Pulse' },
  ];

  return (
    <>
      {/* Top Authoritative Status Strip */}
      <div className="bg-black border-b border-white/[0.06] text-[10px] font-mono text-zinc-500 py-1.5 px-4 sm:px-6 lg:px-8 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
            <span className="text-zinc-400 uppercase tracking-wider">Session Closed · Paper Tape Active</span>
          </div>
          <span className="text-zinc-700">|</span>
          <span className="px-1.5 py-0.5 rounded border border-[#D4AF37]/40 text-[#D4AF37] bg-[#D4AF37]/5 font-semibold text-[9px] uppercase tracking-wider">
            Paper Trading Only
          </span>
        </div>
        <div className="hidden sm:flex items-center gap-4 text-zinc-500">
          <span>{istTime || '15:30:00 IST'}</span>
          <span>NSE NIFTY 500</span>
        </div>
      </div>

      <header className="sticky top-0 z-40 bg-black/95 backdrop-blur-md border-b border-white/[0.08] transition-colors">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-14">
            {/* Brand Mark: Editorial Display Identity */}
            <Link to="/" className="flex items-center gap-2.5 group">
              <span className="text-xl font-display font-medium tracking-tight text-white group-hover:text-[#D4AF37] transition-colors">
                StockMinds<span className="text-zinc-500 font-sans text-xs ml-1.5 font-normal tracking-normal">Benchmark</span>
              </span>
            </Link>

            {/* Desktop Navigation */}
            <nav className="hidden md:flex items-center gap-6 font-mono text-xs">
              {navItems.map(({ to, label, end }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={end}
                  className={({ isActive }) =>
                    `transition-colors relative py-1 ${
                      isActive
                        ? 'text-[#D4AF37] font-semibold'
                        : 'text-zinc-400 hover:text-white'
                    }`
                  }
                >
                  {({ isActive }) => (
                    <>
                      <span>{label}</span>
                      {isActive && (
                        <span className="absolute -bottom-1 left-0 right-0 h-[1.5px] bg-[#D4AF37] transition-all duration-150" />
                      )}
                    </>
                  )}
                </NavLink>
              ))}
            </nav>

            {/* Right Controls: Connection Status Only */}
            <div className="hidden sm:flex items-center gap-3 text-xs font-mono">
              <button
                onClick={handleToggleMock}
                className={`px-2.5 py-1 rounded border transition-colors cursor-pointer text-[10px] font-mono ${
                  !isMock
                    ? isBackendHealthy === false
                      ? 'border-amber-500/40 bg-amber-500/10 text-amber-400 font-semibold'
                      : 'border-emerald-500/40 bg-emerald-500/10 text-emerald-400 font-semibold'
                    : 'border-white/10 text-zinc-400 hover:text-white'
                }`}
                title="Toggle Live backend API / Mock data"
              >
                {!isMock
                  ? isBackendHealthy === false
                    ? '▲ API Offline'
                    : '● Live API'
                  : '○ Mock Mode'}
              </button>
            </div>

            {/* Mobile Menu Button */}
            <div className="md:hidden flex items-center gap-2">
              <button
                onClick={() => setIsHealthOpen(true)}
                className="p-1.5 text-slate-400"
                title="System Health"
              >
                <span className="w-2 h-2 rounded-full bg-emerald-400 block" />
              </button>
              <button
                onClick={() => setIsMenuOpen(!isMenuOpen)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/[0.04]"
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
                    `block px-3 py-2 rounded-lg text-xs font-medium ${
                      isActive
                        ? 'bg-white/[0.08] text-white font-semibold'
                        : 'text-slate-400 hover:text-white hover:bg-white/[0.04]'
                    }`
                  }
                >
                  {label}
                </NavLink>
              ))}

              <div className="pt-2 border-t border-white/10 flex justify-between items-center text-xs px-2 font-mono">
                <span className="text-slate-400 text-[11px]">{istTime}</span>
                <button
                  onClick={handleToggleMock}
                  className="px-2 py-1 rounded bg-white/[0.05] text-slate-300 border border-white/10 text-[11px]"
                >
                  Mode: {isMock ? 'Mock Fixture' : 'Live API'}
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
