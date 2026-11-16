import { TrendingUp, TrendingDown } from 'lucide-react';
import { useEffect, useState } from 'react';

interface MarketIndex {
  name: string;
  value: number;
  change: number;
  changePercent: number;
}

interface TopStock {
  symbol: string;
  name: string;
  price: number;
  change: number;
  changePercent: number;
}

export default function Markets() {
  const [indices, setIndices] = useState<MarketIndex[]>([
    { name: 'NIFTY 50', value: 21853.80, change: 145.30, changePercent: 0.67 },
    { name: 'SENSEX', value: 72240.26, change: 234.12, changePercent: 0.33 },
    { name: 'NIFTY BANK', value: 46789.45, change: -123.45, changePercent: -0.26 },
    { name: 'NIFTY IT', value: 34521.90, change: 287.60, changePercent: 0.84 },
    { name: 'NIFTY MIDCAP', value: 42156.30, change: 312.20, changePercent: 0.75 },
    { name: 'NIFTY PHARMA', value: 18234.55, change: -45.30, changePercent: -0.25 },
  ]);

  const [topGainers] = useState<TopStock[]>([
    { symbol: 'TCS', name: 'Tata Consultancy Services', price: 3654.20, change: 125.30, changePercent: 3.55 },
    { symbol: 'INFY', name: 'Infosys Limited', price: 1432.80, change: 87.45, changePercent: 6.50 },
    { symbol: 'RELIANCE', name: 'Reliance Industries', price: 2847.50, change: 95.20, changePercent: 3.46 },
    { symbol: 'HDFCBANK', name: 'HDFC Bank', price: 1687.90, change: 54.30, changePercent: 3.32 },
    { symbol: 'ICICIBANK', name: 'ICICI Bank', price: 1045.30, change: 42.15, changePercent: 4.20 },
  ]);

  const [topLosers] = useState<TopStock[]>([
    { symbol: 'BAJFINANCE', name: 'Bajaj Finance', price: 6823.40, change: -234.20, changePercent: -3.32 },
    { symbol: 'ASIANPAINT', name: 'Asian Paints', price: 2945.60, change: -87.30, changePercent: -2.88 },
    { symbol: 'MARUTI', name: 'Maruti Suzuki', price: 10234.50, change: -245.60, changePercent: -2.34 },
    { symbol: 'TITAN', name: 'Titan Company', price: 3421.80, change: -78.90, changePercent: -2.25 },
    { symbol: 'TATASTEEL', name: 'Tata Steel', price: 134.25, change: -4.35, changePercent: -3.14 },
  ]);

  useEffect(() => {
    const interval = setInterval(() => {
      setIndices(prev =>
        prev.map(index => {
          const randomChange = (Math.random() - 0.5) * 50;
          const newValue = index.value + randomChange;
          const newChange = index.change + randomChange;
          return {
            ...index,
            value: parseFloat(newValue.toFixed(2)),
            change: parseFloat(newChange.toFixed(2)),
            changePercent: parseFloat(((newChange / (newValue - newChange)) * 100).toFixed(2)),
          };
        })
      );
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="min-h-screen py-12 px-4" style={{ backgroundColor: '#FAF6EF' }}>
      <div className="max-w-7xl mx-auto">

        <div className="mb-12 animate-fade-in-down">
          <p className="text-xs uppercase tracking-widest mb-2 font-medium"
            style={{ fontFamily: "'DM Sans', sans-serif", color: '#C8922A' }}>
            Live Market Data
          </p>
          <h1 className="text-4xl font-normal mb-2"
            style={{ fontFamily: "'Crimson Pro', Georgia, serif", color: '#0F1F3D', fontStyle: 'italic' }}>
            Market Overview
          </h1>
          <p className="text-lg"
            style={{ fontFamily: "'DM Sans', sans-serif", color: '#3D2B00', opacity: 0.55 }}>
            Real-time indices and stock performance — NSE & BSE
          </p>
        </div>

        {/* Indices */}
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6 mb-12">
          {indices.map((index) => {
            const isUp = index.change >= 0;
            return (
              <div key={index.name}
                className="rounded-xl p-6 border transition-all hover:-translate-y-0.5 hover:shadow-md"
                style={{ backgroundColor: '#FFFFFF', borderColor: '#EDE3D0' }}>
                <h3 className="text-sm font-semibold mb-2"
                  style={{ fontFamily: "'DM Sans', sans-serif", color: '#3D2B00', opacity: 0.6 }}>
                  {index.name}
                </h3>
                <p className="text-3xl font-bold my-2"
                  style={{ fontFamily: "'DM Sans', sans-serif", color: '#0F1F3D' }}>
                  {index.value.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                </p>
                <div className="flex items-center space-x-1.5 font-semibold text-sm"
                  style={{ color: isUp ? '#1A7A4A' : '#C0392B' }}>
                  {isUp ? <TrendingUp className="h-4 w-4" /> : <TrendingDown className="h-4 w-4" />}
                  <span>
                    {isUp ? '+' : ''}{index.change.toFixed(2)} ({isUp ? '+' : ''}{index.changePercent.toFixed(2)}%)
                  </span>
                </div>
              </div>
            );
          })}
        </div>

        {/* Gainers / Losers */}
        <div className="grid lg:grid-cols-2 gap-8 mb-8">

          <div className="rounded-xl p-8 border" style={{ backgroundColor: '#FFFFFF', borderColor: '#EDE3D0' }}>
            <h2 className="text-xl font-semibold mb-6 flex items-center space-x-2"
              style={{ fontFamily: "'DM Sans', sans-serif", color: '#0F1F3D' }}>
              <TrendingUp className="h-5 w-5" style={{ color: '#1A7A4A' }} />
              <span>Top Gainers</span>
            </h2>
            <div className="space-y-4">
              {topGainers.map((stock) => (
                <div key={stock.symbol} className="border-b pb-4 last:border-0" style={{ borderColor: '#F0E8D8' }}>
                  <div className="flex justify-between items-start mb-2">
                    <div>
                      <h3 className="font-bold" style={{ fontFamily: "'DM Sans', sans-serif", color: '#0F1F3D' }}>{stock.symbol}</h3>
                      <p className="text-sm" style={{ fontFamily: "'DM Sans', sans-serif", color: '#3D2B00', opacity: 0.55 }}>{stock.name}</p>
                    </div>
                    <div className="text-right">
                      <p className="font-semibold" style={{ fontFamily: "'DM Sans', sans-serif", color: '#0F1F3D' }}>₹{stock.price.toFixed(2)}</p>
                      <p className="text-sm font-semibold" style={{ color: '#1A7A4A' }}>
                        +{stock.change.toFixed(2)} (+{stock.changePercent.toFixed(2)}%)
                      </p>
                    </div>
                  </div>
                  <div className="rounded-full h-1.5" style={{ backgroundColor: '#E8F5EE' }}>
                    <div className="h-1.5 rounded-full transition-all"
                      style={{ width: `${Math.min(stock.changePercent * 10, 100)}%`, backgroundColor: '#1A7A4A' }} />
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-xl p-8 border" style={{ backgroundColor: '#FFFFFF', borderColor: '#EDE3D0' }}>
            <h2 className="text-xl font-semibold mb-6 flex items-center space-x-2"
              style={{ fontFamily: "'DM Sans', sans-serif", color: '#0F1F3D' }}>
              <TrendingDown className="h-5 w-5" style={{ color: '#C0392B' }} />
              <span>Top Losers</span>
            </h2>
            <div className="space-y-4">
              {topLosers.map((stock) => (
                <div key={stock.symbol} className="border-b pb-4 last:border-0" style={{ borderColor: '#F0E8D8' }}>
                  <div className="flex justify-between items-start mb-2">
                    <div>
                      <h3 className="font-bold" style={{ fontFamily: "'DM Sans', sans-serif", color: '#0F1F3D' }}>{stock.symbol}</h3>
                      <p className="text-sm" style={{ fontFamily: "'DM Sans', sans-serif", color: '#3D2B00', opacity: 0.55 }}>{stock.name}</p>
                    </div>
                    <div className="text-right">
                      <p className="font-semibold" style={{ fontFamily: "'DM Sans', sans-serif", color: '#0F1F3D' }}>₹{stock.price.toFixed(2)}</p>
                      <p className="text-sm font-semibold" style={{ color: '#C0392B' }}>
                        {stock.change.toFixed(2)} ({stock.changePercent.toFixed(2)}%)
                      </p>
                    </div>
                  </div>
                  <div className="rounded-full h-1.5" style={{ backgroundColor: '#FDECEA' }}>
                    <div className="h-1.5 rounded-full transition-all"
                      style={{ width: `${Math.min(Math.abs(stock.changePercent) * 10, 100)}%`, backgroundColor: '#C0392B' }} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Highlights */}
        <div className="rounded-xl p-8 border" style={{ backgroundColor: '#FFFFFF', borderColor: '#EDE3D0' }}>
          <h2 className="text-xl font-semibold mb-6"
            style={{ fontFamily: "'DM Sans', sans-serif", color: '#0F1F3D' }}>
            Market Highlights
          </h2>
          <div className="grid md:grid-cols-3 gap-6">
            {[
              { label: 'Total Market Cap', value: '₹328.45 Lakh Cr', sub: '+0.42% today', subColor: '#1A7A4A' },
              { label: 'Trading Volume', value: '₹6,234 Cr', sub: 'NSE + BSE combined', subColor: '#C8922A' },
              { label: 'Advances / Declines', value: '1,245 / 987', sub: 'Bullish breadth', subColor: '#1A7A4A' },
            ].map(({ label, value, sub, subColor }) => (
              <div key={label} className="p-6 rounded-lg border" style={{ borderColor: '#EDE3D0', backgroundColor: '#FAF6EF' }}>
                <p className="text-xs font-medium mb-3 uppercase tracking-wider"
                  style={{ fontFamily: "'DM Sans', sans-serif", color: '#3D2B00', opacity: 0.5 }}>{label}</p>
                <p className="text-2xl font-bold mb-1"
                  style={{ fontFamily: "'DM Sans', sans-serif", color: '#0F1F3D' }}>{value}</p>
                <p className="text-sm font-medium"
                  style={{ fontFamily: "'DM Sans', sans-serif", color: subColor }}>{sub}</p>
              </div>
            ))}
          </div>
        </div>

      </div>
    </div>
  );
}