import { useState, useEffect } from 'react';
import { NavLink, Link } from 'react-router-dom';
import {
  TrendingUp,
  Menu,
  X,
  Server,
  Clock,
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
      <header className="sticky top-0 z-40 bg-[#090B10]/90 backdrop-blur-md border-b border-white/[0.08] transition-colors">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            {/* Brand Mark: Institutional Identity */}
            <Link to="/" className="flex items-center gap-3 group">
              <div className="w-8 h-8 rounded bg-blue-600 flex items-center justify-center text-white shadow-sm transition-transform">
                <TrendingUp className="h-4 w-4" />
              </div>
              <div className="flex flex-col">
                <div className="flex items-center gap-2">
                  <span className="text-base font-display font-bold tracking-tight text-white">
                    StockMinds<span className="text-slate-400 font-normal">.arena</span>
                  </span>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-white/[0.04] text-slate-300 border border-white/10 font-medium">
                    Paper Pilot
                  </span>
                </div>
                <span className="text-[11px] font-mono text-slate-400 -mt-0.5">
                  NSE Nifty 500 · 10 Parallel Strategies
                </span>
              </div>
            </Link>

            {/* Desktop Navigation */}
            <nav className="hidden md:flex items-center gap-1.5 font-sans">
              {navItems.map(({ to, label, badge, end }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={end}
                  className={({ isActive }) =>
                    `px-3.5 py-1.5 rounded-lg text-xs transition-all relative flex items-center gap-1.5 ${
                      isActive
                        ? 'text-white font-semibold bg-white/[0.08]'
                        : 'text-slate-400 hover:text-white hover:bg-white/[0.04]'
                    }`
                  }
                >
                  {({ isActive }) => (
                    <>
                      <span>{label}</span>
                      {badge && (
                        <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-purple-500/20 text-purple-300 border border-purple-500/30">
                          {badge}
                        </span>
                      )}
                      {isActive && (
                        <span className="absolute bottom-0 left-2 right-2 h-[2px] rounded-full bg-blue-500" />
                      )}
                    </>
                  )}
                </NavLink>
              ))}
            </nav>

            {/* Telemetry Status Controls */}
            <div className="hidden sm:flex items-center gap-2.5 text-xs font-mono">
              {/* System Health Drawer Trigger */}
              <button
                onClick={() => setIsHealthOpen(true)}
                className="flex items-center gap-2 px-3 py-1 rounded-lg border border-emerald-500/30 bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/15 transition-colors cursor-pointer"
                title="Click to view scheduled pipeline health"
              >
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                <span className="text-[11px]">10 Jobs Nominal</span>
              </button>

              {/* IST Clock */}
              <div className="flex items-center gap-1.5 text-slate-300 px-3 py-1 bg-white/[0.04] rounded-lg border border-white/10 text-[11px]">
                <Clock className="w-3 h-3 text-slate-500" />
                <span>{istTime || '15:30:00 IST'}</span>
              </div>

              {/* Mock / Live Backend Pill */}
              <button
                onClick={handleToggleMock}
                className={`flex items-center gap-1.5 px-3 py-1 rounded-lg border text-[11px] cursor-pointer transition-colors ${
                  isMock
                    ? 'bg-blue-500/10 text-blue-400 border-blue-500/30'
                    : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                }`}
                title="Click to toggle between mock fixtures and live FastAPI backend"
              >
                <Server className="w-3 h-3" />
                <span>{isMock ? 'Mock Fixture' : 'Live Backend'}</span>
                <span
                  className={`w-1.5 h-1.5 rounded-full ${
                    isMock ? 'bg-blue-400' : isBackendHealthy ? 'bg-emerald-400 animate-pulse' : 'bg-rose-500'
                  }`}
                />
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
