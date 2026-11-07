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
      <header className="sticky top-0 z-40 masthead-panel backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-15">
            {/* Brand Mark: Editorial & Architectural */}
            <Link to="/" className="flex items-center gap-3 group">
              <div className="w-7 h-7 rounded-[3px] bg-[#8A7441] flex items-center justify-center text-white shadow-xs">
                <TrendingUp className="h-3.5 w-3.5" />
              </div>
              <div className="flex flex-col">
                <div className="flex items-center gap-2">
                  <span className="text-base font-serif font-bold tracking-tight text-[#151B26]">
                    StockMinds<span className="text-[#8A7441]">.arena</span>
                  </span>
                  <span className="text-[10px] font-mono px-1.5 py-0.5 rounded-[2px] bg-[#F3EFE6] text-[#8A7441] border border-[#D6C7A1]">
                    Paper Pilot
                  </span>
                </div>
                <span className="text-[10px] font-sans text-[#7C8698] -mt-0.5">
                  Autonomous Multi-Agent Evaluation Arena
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
                    `px-3 py-1.5 rounded-[3px] text-xs transition-colors flex items-center gap-1.5 ${
                      isActive
                        ? 'bg-[#F3EFE6] text-[#8A7441] font-semibold border border-[#D6C7A1]'
                        : 'text-[#475060] hover:text-[#151B26] hover:bg-[#ECE8E0]'
                    }`
                  }
                >
                  <span>{label}</span>
                  {badge && (
                    <span className="text-[9px] font-mono px-1 rounded-[2px] bg-[#F4F0F9] text-[#5E4B7A] border border-[#D3C6E5]">
                      {badge}
                    </span>
                  )}
                </NavLink>
              ))}
            </nav>

            {/* Telemetry Status Controls */}
            <div className="hidden sm:flex items-center gap-2.5 text-xs font-mono">
              {/* System Health Drawer Trigger */}
              <button
                onClick={() => setIsHealthOpen(true)}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded-[3px] border border-[#DCD7CC] bg-[#FFFFFF] hover:bg-[#F6F4EF] text-[#475060] transition-colors cursor-pointer"
                title="Click to view scheduled pipeline health"
              >
                <span className="w-1.5 h-1.5 rounded-full bg-[#1E6548]" />
                <span className="text-[11px]">10 Jobs Nominal</span>
              </button>

              {/* IST Clock */}
              <div className="flex items-center gap-1.5 text-[#475060] px-2.5 py-1 bg-[#F6F4EF] rounded-[3px] border border-[#DCD7CC] text-[11px]">
                <Clock className="w-3 h-3 text-[#7C8698]" />
                <span>{istTime || '15:30:00 IST'}</span>
              </div>

              {/* Mock / Live Backend Pill */}
              <button
                onClick={handleToggleMock}
                className={`flex items-center gap-1.5 px-2.5 py-1 rounded-[3px] border text-[11px] cursor-pointer transition-colors ${
                  isMock
                    ? 'bg-[#EDF2F9] text-[#2A4B7C] border-[#B9C9E1]'
                    : 'bg-[#EBF5F0] text-[#1E6548] border-[#A3D4BE]'
                }`}
                title="Click to toggle between mock fixtures and live FastAPI backend"
              >
                <Server className="w-3 h-3" />
                <span>{isMock ? 'Mock Fixture' : 'Live Backend'}</span>
                <span
                  className={`w-1.5 h-1.5 rounded-full ${
                    isMock ? 'bg-[#2A4B7C]' : isBackendHealthy ? 'bg-[#1E6548] animate-pulse' : 'bg-[#933835]'
                  }`}
                />
              </button>
            </div>

            {/* Mobile Menu Button */}
            <div className="md:hidden flex items-center gap-2">
              <button
                onClick={() => setIsHealthOpen(true)}
                className="p-1.5 text-[#475060]"
                title="System Health"
              >
                <span className="w-2 h-2 rounded-full bg-[#1E6548] block" />
              </button>
              <button
                onClick={() => setIsMenuOpen(!isMenuOpen)}
                className="p-1.5 rounded-[3px] text-[#475060] hover:bg-[#ECE8E0]"
              >
                {isMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
              </button>
            </div>
          </div>

          {/* Mobile Nav Dropdown */}
          {isMenuOpen && (
            <div className="md:hidden py-3 border-t border-[#DCD7CC] space-y-1">
              {navItems.map(({ to, label, end }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={end}
                  onClick={() => setIsMenuOpen(false)}
                  className={({ isActive }) =>
                    `block px-3 py-2 rounded-[3px] text-xs font-medium ${
                      isActive
                        ? 'bg-[#F3EFE6] text-[#8A7441] font-semibold border border-[#D6C7A1]'
                        : 'text-[#475060] hover:bg-[#ECE8E0]'
                    }`
                  }
                >
                  {label}
                </NavLink>
              ))}

              <div className="pt-2 border-t border-[#DCD7CC] flex justify-between items-center text-xs px-2 font-mono">
                <span className="text-[#7C8698] text-[11px]">{istTime}</span>
                <button
                  onClick={handleToggleMock}
                  className="px-2 py-1 rounded-[3px] bg-[#F6F4EF] text-[#475060] border border-[#DCD7CC] text-[11px]"
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
