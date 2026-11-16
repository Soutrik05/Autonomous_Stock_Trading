import { useState } from 'react';
import { IndianRupee, AlertTriangle, TrendingUp, Check } from 'lucide-react';

interface StockSuggestion {
  symbol: string;
  name: string;
  price: number;
  expectedReturn: string;
  confidence: string;
  sector: string;
}

export default function Platform() {
  const [amount, setAmount] = useState('');
  const [risk, setRisk] = useState('medium');
  const [tradeType, setTradeType] = useState('swing');
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [suggestions, setSuggestions] = useState<StockSuggestion[]>([]);

  const generateSuggestions = () => {
    const base: StockSuggestion[] = [
      { symbol: 'RELIANCE', name: 'Reliance Industries', price: 2847.50, expectedReturn: '+8.5%', confidence: 'High', sector: 'Energy' },
      { symbol: 'TCS', name: 'Tata Consultancy Services', price: 3654.20, expectedReturn: '+6.2%', confidence: 'High', sector: 'IT' },
      { symbol: 'INFY', name: 'Infosys Limited', price: 1432.80, expectedReturn: '+7.1%', confidence: 'Medium', sector: 'IT' },
      { symbol: 'HDFCBANK', name: 'HDFC Bank', price: 1687.90, expectedReturn: '+5.8%', confidence: 'High', sector: 'Banking' },
      { symbol: 'ICICIBANK', name: 'ICICI Bank', price: 1045.30, expectedReturn: '+6.9%', confidence: 'Medium', sector: 'Banking' },
    ];
    if (risk === 'high') { base[0].expectedReturn = '+12.5%'; base[2].expectedReturn = '+11.3%'; }
    if (risk === 'low') { base[0].expectedReturn = '+4.2%'; base[2].expectedReturn = '+3.8%'; }
    setSuggestions(base);
    setShowSuggestions(true);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    generateSuggestions();
  };

  const handleAccept = () => {
    alert('Payment gateway integration pending. In production, this would redirect to payment processing.');
  };

  const riskOptions = [
    { val: 'low', label: 'Conservative', sub: 'Steady, safe growth' },
    { val: 'medium', label: 'Balanced', sub: 'Safety + growth mix' },
    { val: 'high', label: 'Aggressive', sub: 'Higher risk, higher reward' },
  ];

  return (
    <div className="min-h-screen py-12 px-4" style={{ backgroundColor: '#FAF6EF' }}>
      <div className="max-w-6xl mx-auto">

        <div className="text-center mb-12 animate-fade-in-down">
          <p className="text-xs uppercase tracking-widest mb-2 font-medium"
            style={{ fontFamily: "'DM Sans', sans-serif", color: '#C8922A' }}>
            AI-Powered Trading
          </p>
          <h1 className="text-4xl font-normal mb-3"
            style={{ fontFamily: "'Crimson Pro', Georgia, serif", color: '#0F1F3D', fontStyle: 'italic' }}>
            Set Your Trading Parameters
          </h1>
          <p className="text-lg"
            style={{ fontFamily: "'DM Sans', sans-serif", color: '#3D2B00', opacity: 0.55 }}>
            Tell us your investment goals and let the AI take it from here
          </p>
        </div>

        <div className="grid lg:grid-cols-2 gap-8">

          {/* LEFT: Inputs */}
          <div className="rounded-3xl p-8 border animate-slide-in-left"
            style={{ backgroundColor: '#FFFFFF', borderColor: '#EDE3D0' }}>
            <h2 className="text-xl font-semibold mb-6"
              style={{ fontFamily: "'DM Sans', sans-serif", color: '#0F1F3D' }}>
              Your Preferences
            </h2>

            <form onSubmit={handleSubmit} className="space-y-6">

              {/* Amount */}
              <div>
                <label className="block text-sm font-semibold mb-2"
                  style={{ fontFamily: "'DM Sans', sans-serif", color: '#0F1F3D' }}>
                  How much would you like to invest?
                </label>
                <div className="relative">
                  <IndianRupee className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5"
                    style={{ color: '#C8922A' }} />
                  <input
                    type="number"
                    value={amount}
                    onChange={(e) => setAmount(e.target.value)}
                    placeholder="Enter amount"
                    className="w-full pl-10 pr-4 py-3 rounded-xl border outline-none transition-all"
                    style={{
                      fontFamily: "'DM Sans', sans-serif",
                      borderColor: '#EDE3D0',
                      backgroundColor: '#FAF6EF',
                      color: '#0F1F3D',
                    }}
                    onFocus={e => (e.target.style.borderColor = '#C8922A')}
                    onBlur={e => (e.target.style.borderColor = '#EDE3D0')}
                    required
                  />
                </div>
                <p className="mt-1.5 text-xs" style={{ fontFamily: "'DM Sans', sans-serif", color: '#C8922A' }}>
                  Minimum: ₹10,000
                </p>
              </div>

              {/* Risk */}
              <div>
                <label className="block text-sm font-semibold mb-3"
                  style={{ fontFamily: "'DM Sans', sans-serif", color: '#0F1F3D' }}>
                  Risk tolerance
                </label>
                <div className="grid grid-cols-3 gap-3">
                  {riskOptions.map(({ val, label, sub }) => (
                    <button key={val} type="button" onClick={() => setRisk(val)}
                      className="py-3 px-2 rounded-xl border-2 text-sm transition-all"
                      style={{
                        fontFamily: "'DM Sans', sans-serif",
                        borderColor: risk === val ? '#C8922A' : '#EDE3D0',
                        backgroundColor: risk === val ? '#FDF3E3' : '#FAF6EF',
                        color: risk === val ? '#C8922A' : '#3D2B00',
                      }}>
                      <div className="font-semibold">{label}</div>
                      <div className="text-xs opacity-55 mt-0.5">{sub}</div>
                    </button>
                  ))}
                </div>
              </div>

              {/* Trade type */}
              <div>
                <label className="block text-sm font-semibold mb-3"
                  style={{ fontFamily: "'DM Sans', sans-serif", color: '#0F1F3D' }}>
                  Trading style
                </label>
                <div className="grid grid-cols-2 gap-4">
                  {[
                    { val: 'swing', label: 'Swing Trading', sub: 'Days to weeks' },
                    { val: 'positional', label: 'Positional', sub: 'Weeks to months' },
                  ].map(({ val, label, sub }) => (
                    <button key={val} type="button" onClick={() => setTradeType(val)}
                      className="py-3 px-4 rounded-xl border-2 transition-all"
                      style={{
                        fontFamily: "'DM Sans', sans-serif",
                        borderColor: tradeType === val ? '#C8922A' : '#EDE3D0',
                        backgroundColor: tradeType === val ? '#FDF3E3' : '#FAF6EF',
                        color: tradeType === val ? '#C8922A' : '#3D2B00',
                      }}>
                      <div className="font-semibold text-sm">{label}</div>
                      <div className="text-xs opacity-55 mt-0.5">{sub}</div>
                    </button>
                  ))}
                </div>
              </div>

              {/* Warning */}
              <div className="flex items-start space-x-3 p-4 rounded-xl border"
                style={{ backgroundColor: '#FFFBF0', borderColor: '#F0D9A8' }}>
                <AlertTriangle className="h-5 w-5 mt-0.5 flex-shrink-0" style={{ color: '#C8922A' }} />
                <p className="text-sm leading-relaxed"
                  style={{ fontFamily: "'Crimson Pro', Georgia, serif", color: '#7A4A00' }}>
                  Trading carries risk. Only invest what you can afford to lose. Past performance does not guarantee future results.
                </p>
              </div>

              <button type="submit"
                className="w-full text-white py-4 rounded-xl font-semibold text-lg transition-all hover:-translate-y-1 hover:shadow-lg"
                style={{
                  background: 'linear-gradient(135deg, #C8922A, #E8A020)',
                  fontFamily: "'DM Sans', sans-serif",
                  boxShadow: '0 4px 16px rgba(200,146,42,0.25)'
                }}>
                See AI Recommendations
              </button>
            </form>
          </div>

          {/* RIGHT: Results */}
          <div className="rounded-3xl p-8 border animate-slide-in-right"
            style={{ backgroundColor: '#FFFFFF', borderColor: '#EDE3D0' }}>
            <h2 className="text-xl font-semibold mb-6"
              style={{ fontFamily: "'DM Sans', sans-serif", color: '#0F1F3D' }}>
              AI Recommendations
            </h2>

            {!showSuggestions ? (
              <div className="flex flex-col items-center justify-center h-64 text-center">
                <div className="w-20 h-20 rounded-2xl flex items-center justify-center mb-4"
                  style={{ backgroundColor: '#FAF6EF', border: '2px dashed #EDE3D0' }}>
                  <TrendingUp className="h-10 w-10" style={{ color: '#EDE3D0' }} />
                </div>
                <p className="text-base"
                  style={{ fontFamily: "'Crimson Pro', Georgia, serif", color: '#3D2B00', opacity: 0.5, fontStyle: 'italic' }}>
                  Fill in your preferences and click the button to get personalised stock picks
                </p>
              </div>
            ) : (
              <div className="space-y-4">

                <div className="p-4 rounded-xl border mb-2"
                  style={{ backgroundColor: '#FDF3E3', borderColor: '#F0D9A8' }}>
                  <p className="text-sm" style={{ fontFamily: "'DM Sans', sans-serif", color: '#7A4A00' }}>
                    Based on your <strong>{risk}</strong> risk level and{' '}
                    <strong>{tradeType === 'swing' ? 'swing trading' : 'positional'}</strong> strategy:
                  </p>
                </div>

                {suggestions.map((stock) => (
                  <div key={stock.symbol}
                    className="border rounded-xl p-4 transition-all hover:-translate-y-0.5 hover:shadow-md"
                    style={{ borderColor: '#EDE3D0', backgroundColor: '#FAF6EF' }}>
                    <div className="flex justify-between items-start mb-2">
                      <div>
                        <div className="flex items-center space-x-2 mb-0.5">
                          <h3 className="font-bold text-lg" style={{ fontFamily: "'DM Sans', sans-serif", color: '#0F1F3D' }}>{stock.symbol}</h3>
                          <span className="text-xs px-2 py-0.5 rounded-full"
                            style={{ backgroundColor: '#E8F5EE', color: '#1A7A4A', fontFamily: "'DM Sans', sans-serif" }}>
                            {stock.sector}
                          </span>
                        </div>
                        <p className="text-sm" style={{ fontFamily: "'DM Sans', sans-serif", color: '#3D2B00', opacity: 0.55 }}>{stock.name}</p>
                      </div>
                      <div className="text-right">
                        <p className="font-semibold" style={{ fontFamily: "'DM Sans', sans-serif", color: '#0F1F3D' }}>₹{stock.price.toFixed(2)}</p>
                        <span className="text-sm font-semibold" style={{ color: '#1A7A4A' }}>{stock.expectedReturn}</span>
                      </div>
                    </div>
                    <div className="flex items-center justify-between mt-3 pt-3 border-t" style={{ borderColor: '#EDE3D0' }}>
                      <span className="text-xs" style={{ fontFamily: "'DM Sans', sans-serif", color: '#3D2B00', opacity: 0.45 }}>AI Confidence</span>
                      <span className="text-xs font-semibold px-2 py-1 rounded-lg"
                        style={{
                          backgroundColor: stock.confidence === 'High' ? '#E8F5EE' : '#FDF3E3',
                          color: stock.confidence === 'High' ? '#1A7A4A' : '#C8922A',
                          fontFamily: "'DM Sans', sans-serif"
                        }}>
                        {stock.confidence}
                      </span>
                    </div>
                  </div>
                ))}

                <div className="mt-6 pt-6 border-t" style={{ borderColor: '#EDE3D0' }}>
                  <div className="rounded-xl p-4 mb-4 border" style={{ backgroundColor: '#FAF6EF', borderColor: '#EDE3D0' }}>
                    {[
                      { label: 'Investment', val: `₹${Number(amount).toLocaleString('en-IN')}`, color: '#0F1F3D' },
                      { label: 'Stocks Selected', val: `${suggestions.length}`, color: '#0F1F3D' },
                      { label: 'Expected Return', val: '+7.2%', color: '#1A7A4A' },
                    ].map(({ label, val, color }) => (
                      <div key={label} className="flex justify-between items-center py-1.5">
                        <span className="text-sm" style={{ fontFamily: "'DM Sans', sans-serif", color: '#3D2B00', opacity: 0.6 }}>{label}</span>
                        <span className="font-bold" style={{ fontFamily: "'DM Sans', sans-serif", color }}>{val}</span>
                      </div>
                    ))}
                  </div>

                  <button onClick={handleAccept}
                    className="w-full text-white py-4 rounded-xl font-semibold text-lg flex items-center justify-center space-x-2 transition-all hover:-translate-y-1 hover:shadow-lg"
                    style={{
                      background: 'linear-gradient(135deg, #1A7A4A, #22A05F)',
                      fontFamily: "'DM Sans', sans-serif",
                      boxShadow: '0 4px 16px rgba(26,122,74,0.25)'
                    }}>
                    <Check className="h-5 w-5" />
                    <span>Proceed to Payment</span>
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}