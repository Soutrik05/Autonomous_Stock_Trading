import { useState, useEffect } from 'react';
import { NavLink, Link } from 'react-router-dom';
import {
  TrendingUp,
  Activity,
  GitCompare,
  History,
  ShieldCheck,
  Menu,
  X,
  Server,
  Clock,
  Users,
} from 'lucide-react';
import { getIsMockMode, setMockMode, apiService } from '../services/api';

export default function Header() {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
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
    { to: '/', label: 'Leaderboard', icon: TrendingUp },
    { to: '/agents/simons', label: 'Agent Cockpit', icon: Users },
    { to: '/comparison', label: 'Baseline Compare', icon: GitCompare },
    { to: '/activity', label: 'Transparency Feed', icon: Activity },
    { to: '/backtest', label: 'Backtest Lab', icon: History, badge: 'WEEK 4' },
    { to: '/health', label: 'System Health', icon: ShieldCheck },
  ];

  return (
    <header className="sticky top-0 z-50 bg-white/95 dark:bg-stone-900/95 backdrop-blur-md border-b border-stone-200 dark:border-stone-800 shadow-xs">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          {/* Brand Identity */}
          <Link to="/" className="flex items-center gap-3 group">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-amber-600 via-amber-500 to-amber-400 flex items-center justify-center shadow-sm">
              <TrendingUp className="h-5 w-5 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xl font-bold tracking-tight text-stone-900 dark:text-stone-100 font-mono">
                  StockMinds<span className="text-amber-500">.ai</span>
                </span>
                <span className="text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300">
                  Paper Trading
                </span>
              </div>
              <div className="text-[10px] text-stone-400 dark:text-stone-500 flex items-center gap-1 font-mono">
                <span>Autonomous LLM Multi-Agent System</span>
              </div>
            </div>
          </Link>

          {/* Desktop Navigation */}
          <nav className="hidden lg:flex items-center gap-1">
            {navItems.map(({ to, label, icon: Icon, badge }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  `px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-all ${
                    isActive
                      ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400 font-semibold'
                      : 'text-stone-600 dark:text-stone-300 hover:bg-stone-100 dark:hover:bg-stone-800'
                  }`
                }
              >
                <Icon className="w-3.5 h-3.5" />
                <span>{label}</span>
                {badge && (
                  <span className="text-[9px] px-1 rounded bg-stone-100 dark:bg-stone-800 text-stone-500">
                    {badge}
                  </span>
                )}
              </NavLink>
            ))}
          </nav>

          {/* System Telemetry & Mode Pill */}
          <div className="hidden sm:flex items-center gap-3 text-xs font-mono">
            {/* IST Clock */}
            <div className="flex items-center gap-1 text-stone-500 dark:text-stone-400 px-2 py-1 bg-stone-100 dark:bg-stone-800/80 rounded-md">
              <Clock className="w-3 h-3 text-stone-400" />
              <span>{istTime || '15:30:00 IST'}</span>
            </div>

            {/* Mock / Live Backend Switch */}
            <button
              onClick={handleToggleMock}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md border text-xs cursor-pointer transition-all ${
                isMock
                  ? 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/40 dark:text-blue-300 dark:border-blue-800'
                  : 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800'
              }`}
              title="Click to toggle between frontend mock data fixtures and live FastAPI backend."
            >
              <Server className="w-3 h-3" />
              <span>{isMock ? 'Mock API Fixture' : 'Live REST API'}</span>
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  isMock ? 'bg-blue-500' : isBackendHealthy ? 'bg-emerald-500 animate-pulse' : 'bg-rose-500'
                }`}
              />
            </button>
          </div>

          {/* Mobile Menu Button */}
          <div className="lg:hidden flex items-center gap-2">
            <button
              onClick={() => setIsMenuOpen(!isMenuOpen)}
              className="p-2 rounded-lg text-stone-600 dark:text-stone-300 hover:bg-stone-100 dark:hover:bg-stone-800"
            >
              {isMenuOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
            </button>
          </div>
        </div>

        {/* Mobile Dropdown */}
        {isMenuOpen && (
          <div className="lg:hidden py-3 border-t border-stone-200 dark:border-stone-800 space-y-1">
            {navItems.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                onClick={() => setIsMenuOpen(false)}
                className={({ isActive }) =>
                  `block px-3 py-2 rounded-lg text-sm font-medium flex items-center gap-2 ${
                    isActive
                      ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400 font-semibold'
                      : 'text-stone-600 dark:text-stone-300 hover:bg-stone-100 dark:hover:bg-stone-800'
                  }`
                }
              >
                <Icon className="w-4 h-4" />
                <span>{label}</span>
              </NavLink>
            ))}

            <div className="pt-2 border-t border-stone-200 dark:border-stone-800 flex justify-between items-center text-xs px-2">
              <span className="text-stone-400 font-mono">{istTime}</span>
              <button
                onClick={handleToggleMock}
                className="px-2 py-1 rounded bg-stone-100 dark:bg-stone-800 text-stone-700 dark:text-stone-300 font-mono text-[11px]"
              >
                Toggle {isMock ? 'Mock' : 'Live'}
              </button>
            </div>
          </div>
        )}
      </div>
    </header>
  );
}
