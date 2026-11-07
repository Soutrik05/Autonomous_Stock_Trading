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
    { to: '/', label: 'Home', end: true },
    { to: '/leaderboard', label: 'Leaderboard' },
    { to: '/portfolio/simons', label: 'Portfolio' },
    { to: '/comparison', label: 'Comparison' },
    { to: '/backtest', label: 'Backtest', badge: 'WEEK 4' },
    { to: '/pulse', label: 'Pulse' },
  ];

  return (
    <>
      <header className="sticky top-0 z-40 bg-[#FAF9F6]/95 backdrop-blur-md border-b border-[#E5E2D9] shadow-xs">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            {/* Brand Mark */}
            <Link to="/" className="flex items-center gap-3 group">
              <div className="w-8 h-8 rounded-lg bg-[#D97706] flex items-center justify-center text-white shadow-xs">
                <TrendingUp className="h-4 w-4" />
              </div>
              <div className="flex flex-col">
                <div className="flex items-center gap-1.5">
                  <span className="text-lg font-serif font-bold tracking-tight text-[#111827]">
                    StockMinds<span className="text-[#D97706]">.ai</span>
                  </span>
                  <span className="text-[9px] font-mono font-semibold uppercase px-1.5 py-0.2 rounded bg-amber-100/70 text-amber-800 border border-amber-200/60">
                    Paper Trading
                  </span>
                </div>
                <span className="text-[10px] font-mono text-[#9CA3AF] -mt-0.5">
                  Autonomous Multi-Agent Evaluation
                </span>
              </div>
            </Link>

            {/* Desktop Navigation */}
            <nav className="hidden md:flex items-center gap-1 font-sans">
              {navItems.map(({ to, label, badge, end }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={end}
                  className={({ isActive }) =>
                    `px-3 py-1.5 rounded-lg text-xs font-medium transition-all flex items-center gap-1.5 ${
                      isActive
                        ? 'bg-amber-500/10 text-amber-800 font-semibold border border-amber-200/60'
                        : 'text-[#4B5563] hover:text-[#111827] hover:bg-[#F4F2EC]'
                    }`
                  }
                >
                  <span>{label}</span>
                  {badge && (
                    <span className="text-[9px] font-mono px-1 rounded bg-purple-100 text-purple-700">
                      {badge}
                    </span>
                  )}
                </NavLink>
              ))}
            </nav>

            {/* Telemetry Status Controls */}
            <div className="hidden sm:flex items-center gap-3 text-xs font-mono">
              {/* System Health Drawer Trigger */}
              <button
                onClick={() => setIsHealthOpen(true)}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded-md border border-[#E5E2D9] bg-white hover:bg-[#F4F2EC] text-[#4B5563] transition-colors cursor-pointer"
                title="Click to view scheduled pipeline health"
              >
                <span className="w-2 h-2 rounded-full bg-emerald-500" />
                <span>10 Jobs Nominal</span>
              </button>

              {/* IST Clock */}
              <div className="flex items-center gap-1.5 text-[#4B5563] px-2.5 py-1 bg-[#F4F2EC] rounded-md border border-[#EDEAE2]">
                <Clock className="w-3 h-3 text-[#9CA3AF]" />
                <span>{istTime || '15:30:00 IST'}</span>
              </div>

              {/* Mock / Live Backend Pill */}
              <button
                onClick={handleToggleMock}
                className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md border text-xs cursor-pointer transition-all ${
                  isMock
                    ? 'bg-blue-50 text-blue-700 border-blue-200'
                    : 'bg-emerald-50 text-emerald-700 border-emerald-200'
                }`}
                title="Click to toggle between mock fixtures and live FastAPI backend"
              >
                <Server className="w-3 h-3" />
                <span>{isMock ? 'Mock API' : 'Live API'}</span>
                <span
                  className={`w-1.5 h-1.5 rounded-full ${
                    isMock ? 'bg-blue-500' : isBackendHealthy ? 'bg-emerald-500 animate-pulse' : 'bg-rose-500'
                  }`}
                />
              </button>
            </div>

            {/* Mobile Menu Button */}
            <div className="md:hidden flex items-center gap-2">
              <button
                onClick={() => setIsHealthOpen(true)}
                className="p-1.5 text-[#4B5563]"
                title="System Health"
              >
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 block" />
              </button>
              <button
                onClick={() => setIsMenuOpen(!isMenuOpen)}
                className="p-2 rounded-lg text-[#4B5563] hover:bg-[#F4F2EC]"
              >
                {isMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
              </button>
            </div>
          </div>

          {/* Mobile Nav Dropdown */}
          {isMenuOpen && (
            <div className="md:hidden py-3 border-t border-[#E5E2D9] space-y-1">
              {navItems.map(({ to, label, end }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={end}
                  onClick={() => setIsMenuOpen(false)}
                  className={({ isActive }) =>
                    `block px-3 py-2 rounded-lg text-sm font-medium ${
                      isActive
                        ? 'bg-amber-500/10 text-amber-800 font-semibold'
                        : 'text-[#4B5563] hover:bg-[#F4F2EC]'
                    }`
                  }
                >
                  {label}
                </NavLink>
              ))}

              <div className="pt-2 border-t border-[#E5E2D9] flex justify-between items-center text-xs px-2 font-mono">
                <span className="text-[#9CA3AF]">{istTime}</span>
                <button
                  onClick={handleToggleMock}
                  className="px-2 py-1 rounded bg-[#F4F2EC] text-[#4B5563] border border-[#E5E2D9]"
                >
                  Mode: {isMock ? 'Mock' : 'Live'}
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
