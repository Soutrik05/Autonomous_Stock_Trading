import { Link } from 'react-router-dom';
import { TrendingUp, Menu, X } from 'lucide-react';
import { useState } from 'react';

export default function Header() {
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  return (
    <header className="sticky top-0 z-50 border-b border-amber-100/60 backdrop-blur-sm"
      style={{ background: 'linear-gradient(to right, #FAF6EF, #FDF8F2, #FAF6EF)' }}>
      <nav className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">

          {/* Brand — Hindi identity only here */}
          <Link to="/" className="flex items-center space-x-2.5 group">
            <div className="relative">
              <div className="w-9 h-9 rounded-lg flex items-center justify-center"
                style={{ background: 'linear-gradient(135deg, #C8922A, #E8A020)' }}>
                <TrendingUp className="h-5 w-5 text-white" />
              </div>
              <div className="absolute inset-0 rounded-lg opacity-0 group-hover:opacity-40 transition-opacity blur-md"
                style={{ backgroundColor: '#C8922A' }} />
            </div>
            <div className="flex flex-col leading-none">
              <span className="text-xl font-normal tracking-tight"
                style={{ fontFamily: "'Tiro Devanagari Hindi', serif", color: '#0F1F3D' }}>
                व्यापार<span style={{ color: '#C8922A' }}>AI</span>
              </span>
              <span className="text-[9px] tracking-widest uppercase"
                style={{ fontFamily: "'DM Sans', sans-serif", color: '#C8922A', letterSpacing: '0.12em' }}>
                Smart Trading · स्मार्ट निवेश
              </span>
            </div>
          </Link>

          {/* Desktop Nav — English */}
          <div className="hidden md:flex items-center space-x-8">
            {[
              { to: '/', label: 'Home' },
              { to: '/platform', label: 'Trading Platform' },
              { to: '/markets', label: 'Markets' },
              { to: '/insights', label: 'Insights' },
            ].map(({ to, label }) => (
              <Link key={to} to={to}
                className="relative group transition-colors duration-300 font-medium text-sm"
                style={{ fontFamily: "'DM Sans', sans-serif", color: '#3D2B00' }}>
                {label}
                <span className="absolute bottom-0 left-0 w-0 h-0.5 group-hover:w-full transition-all duration-300 rounded-full"
                  style={{ background: 'linear-gradient(to right, #C8922A, #E8A020)' }} />
              </Link>
            ))}
            <Link to="/platform"
              className="text-white px-6 py-2 rounded-lg font-medium text-sm transition-all duration-300 hover:shadow-lg hover:-translate-y-0.5 transform"
              style={{
                background: 'linear-gradient(135deg, #C8922A, #E8A020)',
                fontFamily: "'DM Sans', sans-serif",
                boxShadow: '0 2px 12px rgba(200,146,42,0.3)'
              }}>
              Get Started
            </Link>
          </div>

          <button className="md:hidden" style={{ color: '#0F1F3D' }}
            onClick={() => setIsMenuOpen(!isMenuOpen)}>
            {isMenuOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
          </button>
        </div>

        {isMenuOpen && (
          <div className="md:hidden py-4 space-y-3 border-t border-amber-100 mt-1">
            {[
              { to: '/', label: 'Home' },
              { to: '/platform', label: 'Trading Platform' },
              { to: '/markets', label: 'Markets' },
              { to: '/insights', label: 'Insights' },
            ].map(({ to, label }) => (
              <Link key={to} to={to}
                className="block font-medium py-1"
                style={{ fontFamily: "'DM Sans', sans-serif", color: '#3D2B00' }}
                onClick={() => setIsMenuOpen(false)}>
                {label}
              </Link>
            ))}
            <Link to="/platform"
              className="block text-white px-6 py-2.5 rounded-lg font-medium text-center mt-2"
              style={{ background: 'linear-gradient(135deg, #C8922A, #E8A020)', fontFamily: "'DM Sans', sans-serif" }}
              onClick={() => setIsMenuOpen(false)}>
              Get Started
            </Link>
          </div>
        )}
      </nav>
    </header>
  );
}