import { Link } from 'react-router-dom';
import { Bot, Shield, TrendingUp, Zap, BarChart3, Clock } from 'lucide-react';

const featureCards = [
  {
    icon: Bot,
    iconColor: '#C8922A',
    bgFrom: '#FDF3E3',
    bgTo: '#FEF9F0',
    title: 'Smart Analysis',
    desc: 'Our AI analyzes market patterns and trends to identify high-potential opportunities before they become obvious.',
    delay: '0.1s',
  },
  {
    icon: Shield,
    iconColor: '#1A7A4A',
    bgFrom: '#E8F5EE',
    bgTo: '#F0FAF4',
    title: 'Risk Control',
    desc: 'Set your comfort level once. The system manages your risk automatically across every trade.',
    delay: '0.2s',
  },
  
 
  {
    icon: BarChart3,
    iconColor: '#C8922A',
    bgFrom: '#FDF3E3',
    bgTo: '#FEF9F0',
    title: 'Clear Insights',
    desc: 'Track performance with detailed analytics updated in real-time. No jargon, just clarity.',
    delay: '0.5s',
  },

];

export default function Home() {
  return (
    <div className="overflow-hidden" style={{ backgroundColor: '#FAF6EF' }}>

      {/* Hero */}
      <section className="relative py-24 px-4 md:py-32">
        <div className="absolute inset-0 opacity-[0.04] pointer-events-none">
          <div className="absolute top-0 left-1/4 w-96 h-96 rounded-full blur-3xl" style={{ backgroundColor: '#C8922A' }} />
          <div className="absolute bottom-0 right-1/4 w-96 h-96 rounded-full blur-3xl" style={{ backgroundColor: '#E8A020' }} />
        </div>

        <div className="relative max-w-7xl mx-auto">
          <div className="grid md:grid-cols-2 gap-12 items-center">

            <div className="animate-fade-in-up">
              <p className="text-xs uppercase tracking-widest mb-4 font-medium"
                style={{ fontFamily: "'DM Sans', sans-serif", color: '#C8922A' }}>
                
              </p>
              {/* Brand headline — Hindi here gives identity without confusing anyone */}
              <h1 className="text-5xl md:text-6xl font-normal leading-tight mb-3"
                style={{ fontFamily: "'Tiro Devanagari Hindi', serif", color: '#0F1F3D' }}>
                व्यापार<span style={{ color: '#C8922A' }}>AI</span>
              </h1>
              <h2 className="text-3xl md:text-4xl font-normal leading-snug mb-6"
                style={{ fontFamily: "'Crimson Pro', Georgia, serif", color: '#0F1F3D', fontStyle: 'italic' }}>
                Trade smarter, <span style={{ color: '#C8922A' }}>not harder.</span>
              </h2>
              <p className="text-lg mb-8 leading-relaxed"
                style={{ fontFamily: "'Crimson Pro', Georgia, serif", color: '#3D2B00', opacity: 0.75 }}>
                Let AI handle the complex task. You tell us how much to invest, We will find the best oppurtunities for you.
              </p>
              <div className="flex flex-col sm:flex-row gap-4">
                <Link to="/platform"
                  className="px-8 py-4 rounded-xl text-white font-semibold text-center transition-all hover:-translate-y-1 hover:shadow-lg"
                  style={{
                    background: 'linear-gradient(135deg, #C8922A, #E8A020)',
                    fontFamily: "'DM Sans', sans-serif",
                    boxShadow: '0 4px 16px rgba(200,146,42,0.3)'
                  }}>
                  Start Trading
                </Link>
                <Link to="/insights"
                  className="px-8 py-4 rounded-xl font-semibold text-center transition-all hover:-translate-y-1 border-2"
                  style={{
                    fontFamily: "'DM Sans', sans-serif",
                    borderColor: '#0F1F3D',
                    color: '#0F1F3D',
                  }}>
                  Read Insights
                </Link>
              </div>
            </div>

            {/* Stats card */}
            <div className="hidden md:block animate-slide-in-right">
              <div className="relative">
                <div className="absolute inset-0 rounded-3xl blur-2xl opacity-20"
                  style={{ background: 'linear-gradient(135deg, #C8922A, #E8A020)' }} />
                <div className="relative p-8 rounded-3xl shadow-2xl border"
                  style={{ backgroundColor: '#FFFFFF', borderColor: '#F0E8D8' }}>
                  <p className="text-xs uppercase tracking-widest mb-6 font-medium"
                    style={{ fontFamily: "'DM Sans', sans-serif", color: '#C8922A' }}>
                    Live Portfolio
                  </p>
                  <div className="space-y-4">
                    <div className="flex items-center justify-between p-4 rounded-xl border"
                      style={{ background: 'linear-gradient(to right, #E8F5EE, #F0FAF4)', borderColor: '#C5E3D1' }}>
                      <span className="font-medium" style={{ fontFamily: "'DM Sans', sans-serif", color: '#0F1F3D' }}>Portfolio Value</span>
                      <span className="text-2xl font-bold" style={{ fontFamily: "'DM Sans', sans-serif", color: '#1A7A4A' }}>₹1,03,84,000</span>
                    </div>
                    <div className="flex items-center justify-between p-4 rounded-xl border"
                      style={{ background: 'linear-gradient(to right, #FDF3E3, #FEF9F0)', borderColor: '#F0D9A8' }}>
                      <span className="font-medium" style={{ fontFamily: "'DM Sans', sans-serif", color: '#0F1F3D' }}>Today's Gain</span>
                      <span className="text-2xl font-bold" style={{ fontFamily: "'DM Sans', sans-serif", color: '#C8922A' }}>+₹2,36,900</span>
                    </div>
                    <div className="flex items-center justify-between p-4 rounded-xl border"
                      style={{ backgroundColor: '#F8F4EE', borderColor: '#E8DCC8' }}>
                      <span className="font-medium" style={{ fontFamily: "'DM Sans', sans-serif", color: '#0F1F3D' }}>Active Trades</span>
                      <span className="text-2xl font-bold" style={{ fontFamily: "'DM Sans', sans-serif", color: '#0F1F3D' }}>12</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

          </div>
        </div>
      </section>

      {/* Features */}
      <section className="py-24 px-4" style={{ background: 'linear-gradient(to bottom, #F5EFE3, #FAF6EF)' }}>
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16 animate-fade-in-up">
            <h2 className="text-4xl font-normal mb-3"
              style={{ fontFamily: "'Crimson Pro', Georgia, serif", color: '#0F1F3D', fontStyle: 'italic' }}>
              Why traders choose <span style={{ color: '#C8922A', fontStyle: 'normal', fontFamily: "'Tiro Devanagari Hindi', serif" }}>व्यापारAI</span>
            </h2>
            <p className="text-lg"
              style={{ fontFamily: "'DM Sans', sans-serif", color: '#3D2B00', opacity: 0.55 }}>
              Everything you need to trade with confidence
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            {featureCards.map(({ icon: Icon, iconColor, bgFrom, bgTo, title, desc, delay }) => (
              <div key={title}
                className="p-8 rounded-2xl border transition-all hover:-translate-y-1 hover:shadow-lg animate-fade-in-up"
                style={{ backgroundColor: '#FFFFFF', borderColor: '#EDE3D0', animationDelay: delay }}>
                <div className="w-14 h-14 rounded-xl flex items-center justify-center mb-5"
                  style={{ background: `linear-gradient(135deg, ${bgFrom}, ${bgTo})` }}>
                  <Icon className="h-7 w-7" style={{ color: iconColor }} />
                </div>
                <h3 className="text-lg font-semibold mb-3"
                  style={{ fontFamily: "'DM Sans', sans-serif", color: '#0F1F3D' }}>
                  {title}
                </h3>
                <p className="leading-relaxed text-base"
                  style={{ fontFamily: "'Crimson Pro', Georgia, serif", color: '#3D2B00', opacity: 0.7 }}>
                  {desc}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-24 px-4 relative overflow-hidden"
        style={{ background: 'linear-gradient(135deg, #0F1F3D, #1A3366)' }}>
        <div className="absolute top-0 right-0 w-96 h-96 rounded-full blur-3xl opacity-10"
          style={{ backgroundColor: '#C8922A' }} />
        <div className="relative max-w-4xl mx-auto text-center">
          <h2 className="text-4xl font-normal mb-4 animate-fade-in-up"
            style={{ fontFamily: "'Crimson Pro', Georgia, serif", color: '#FAF6EF', fontStyle: 'italic' }}>
            Ready to get started?
          </h2>
          <p className="text-lg mb-10 animate-fade-in-up"
            style={{ fontFamily: "'DM Sans', sans-serif", color: '#C8A87A', animationDelay: '0.1s' }}>
            Join thousands of traders making smarter investment decisions across India
          </p>
          <Link to="/platform"
            className="inline-block px-10 py-4 rounded-xl font-semibold text-lg transition-all hover:-translate-y-1 hover:shadow-2xl animate-fade-in-up"
            style={{
              background: 'linear-gradient(135deg, #C8922A, #E8A020)',
              color: '#FFFFFF',
              fontFamily: "'DM Sans', sans-serif",
              animationDelay: '0.2s'
            }}>
            Launch Platform
          </Link>
        </div>
      </section>
    </div>
  );
}