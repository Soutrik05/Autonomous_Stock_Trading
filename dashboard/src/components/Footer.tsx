import { Link } from 'react-router-dom';
import { TrendingUp, Mail, Phone, MapPin } from 'lucide-react';

export default function Footer() {
  return (
    <footer className="border-t border-amber-900/20 text-amber-100"
      style={{ background: 'linear-gradient(to bottom, #0F1F3D, #081630)' }}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8">

          {/* Brand block — Hindi name + tagline only */}
          <div className="animate-fade-in-up">
            <div className="flex items-center space-x-2.5 mb-4">
              <div className="w-9 h-9 rounded-lg flex items-center justify-center"
                style={{ background: 'linear-gradient(135deg, #C8922A, #E8A020)' }}>
                <TrendingUp className="h-5 w-5 text-white" />
              </div>
              <div className="flex flex-col leading-none">
                <span className="text-xl font-normal"
                  style={{ fontFamily: "'Tiro Devanagari Hindi', serif", color: '#FAF6EF' }}>
                  व्यापार<span style={{ color: '#E8A020' }}>AI</span>
                </span>
                <span className="text-[9px] tracking-widest uppercase"
                  style={{ fontFamily: "'DM Sans', sans-serif", color: '#C8922A' }}>
                  Smart Trading · स्मार्ट निवेश
                </span>
              </div>
            </div>
            <p className="text-sm leading-relaxed text-amber-200/70"
              style={{ fontFamily: "'Crimson Pro', Georgia, serif" }}>
              India's AI-powered autonomous trading platform. Smart analysis, smarter decisions.
            </p>
          </div>

          {/* Platform links */}
          <div className="animate-fade-in-up" style={{ animationDelay: '0.1s' }}>
            <h3 className="font-semibold mb-4 text-amber-100"
              style={{ fontFamily: "'DM Sans', sans-serif" }}>Platform</h3>
            <div className="space-y-2">
              {[
                { to: '/', label: 'Home' },
                { to: '/platform', label: 'Start Trading' },
                { to: '/markets', label: 'Markets' },
                { to: '/insights', label: 'Insights' },
              ].map(({ to, label }) => (
                <Link key={to} to={to}
                  className="block text-sm text-amber-200/60 hover:text-amber-300 transition-colors duration-200"
                  style={{ fontFamily: "'DM Sans', sans-serif" }}>
                  {label}
                </Link>
              ))}
            </div>
          </div>

          {/* Legal */}
          <div className="animate-fade-in-up" style={{ animationDelay: '0.2s' }}>
            <h3 className="font-semibold mb-4 text-amber-100"
              style={{ fontFamily: "'DM Sans', sans-serif" }}>Legal</h3>
            <div className="space-y-2">
              {['Privacy Policy', 'Terms of Service', 'Risk Warning', 'Compliance'].map(item => (
                <a key={item} href="#"
                  className="block text-sm text-amber-200/60 hover:text-amber-300 transition-colors duration-200"
                  style={{ fontFamily: "'DM Sans', sans-serif" }}>
                  {item}
                </a>
              ))}
            </div>
          </div>

          {/* Contact */}
          <div className="animate-fade-in-up" style={{ animationDelay: '0.3s' }}>
            <h3 className="font-semibold mb-4 text-amber-100"
              style={{ fontFamily: "'DM Sans', sans-serif" }}>Contact Us</h3>
            <div className="space-y-3">
              {[
                { icon: Mail, text: 'support@vyaparai.in' },
                { icon: Phone, text: '+91 98765 43210' },
                { icon: MapPin, text: 'Mumbai, Maharashtra' },
              ].map(({ icon: Icon, text }) => (
                <div key={text} className="flex items-center space-x-2 text-sm text-amber-200/60 hover:text-amber-300 transition-colors cursor-pointer">
                  <Icon className="h-4 w-4 flex-shrink-0" />
                  <span style={{ fontFamily: "'DM Sans', sans-serif" }}>{text}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="border-t border-amber-900/30 mt-12 pt-8 text-center">
          <p className="text-sm text-amber-200/50"
            style={{ fontFamily: "'DM Sans', sans-serif" }}>
            &copy; 2024 व्यापारAI. All rights reserved.
          </p>
          <p className="mt-2 text-xs text-amber-200/30"
            style={{ fontFamily: "'Crimson Pro', Georgia, serif", fontStyle: 'italic' }}>
            Trading involves risk. Only invest what you can afford to lose.
          </p>
        </div>
      </div>
    </footer>
  );
}