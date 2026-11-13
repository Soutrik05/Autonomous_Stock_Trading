import { Calendar, Clock, User, TrendingUp } from 'lucide-react';
import { useState } from 'react';

interface Article {
  id: number;
  title: string;
  excerpt: string;
  author: string;
  date: string;
  readTime: string;
  category: string;
  image: string;
}

const categoryAccent: Record<string, string> = {
  'Market Analysis': '#1A7A4A',
  'Stock Picks': '#C8922A',
  'Technology': '#0F1F3D',
  'Education': '#1A7A4A',
  'Sector Analysis': '#C8922A',
  'Investment Strategy': '#0F1F3D',
};

export default function Insights() {
  const [activeCategory, setActiveCategory] = useState('All');

  const articles: Article[] = [
    {
      id: 1,
      title: 'Navigating Market Volatility',
      excerpt: 'Market swings happen. Here\'s how to stay calm and make smarter trades when things get chaotic.',
      author: 'Dr. Rajesh Kumar',
      date: 'March 28, 2024',
      readTime: '5 min read',
      category: 'Market Analysis',
      image: 'https://images.pexels.com/photos/6801648/pexels-photo-6801648.jpeg?auto=compress&cs=tinysrgb&w=800',
    },
    {
      id: 2,
      title: 'Top Stocks to Watch This Quarter',
      excerpt: 'We\'ve identified five stocks with strong growth potential based on market trends and fundamentals.',
      author: 'Priya Sharma',
      date: 'March 26, 2024',
      readTime: '7 min read',
      category: 'Stock Picks',
      image: 'https://images.pexels.com/photos/7567443/pexels-photo-7567443.jpeg?auto=compress&cs=tinysrgb&w=800',
    },
    {
      id: 3,
      title: 'How AI is Changing Trading',
      excerpt: 'Artificial intelligence is making trading faster and smarter. Here\'s what you need to know.',
      author: 'Amit Patel',
      date: 'March 24, 2024',
      readTime: '6 min read',
      category: 'Technology',
      image: 'https://images.pexels.com/photos/8370752/pexels-photo-8370752.jpeg?auto=compress&cs=tinysrgb&w=800',
    },
    {
      id: 4,
      title: 'Risk Management 101',
      excerpt: 'The key to long-term success in trading isn\'t big wins — it\'s protecting yourself from big losses.',
      author: 'Sarah Johnson',
      date: 'March 22, 2024',
      readTime: '8 min read',
      category: 'Education',
      image: 'https://images.pexels.com/photos/6801874/pexels-photo-6801874.jpeg?auto=compress&cs=tinysrgb&w=800',
    },
    {
      id: 5,
      title: 'Banking Sector Trends',
      excerpt: 'A detailed look at what\'s happening in Indian banking and which stocks might benefit.',
      author: 'Dr. Rajesh Kumar',
      date: 'March 20, 2024',
      readTime: '10 min read',
      category: 'Sector Analysis',
      image: 'https://images.pexels.com/photos/6801642/pexels-photo-6801642.jpeg?auto=compress&cs=tinysrgb&w=800',
    },
    {
      id: 6,
      title: 'Building Wealth with Dividends',
      excerpt: 'Learn how to build a steady income stream by investing in dividend-paying stocks.',
      author: 'Priya Sharma',
      date: 'March 18, 2024',
      readTime: '6 min read',
      category: 'Investment Strategy',
      image: 'https://images.pexels.com/photos/7567442/pexels-photo-7567442.jpeg?auto=compress&cs=tinysrgb&w=800',
    },
  ];

  const categories = ['All', 'Market Analysis', 'Stock Picks', 'Technology', 'Education', 'Sector Analysis', 'Investment Strategy'];
  const filtered = activeCategory === 'All' ? articles : articles.filter(a => a.category === activeCategory);

  return (
    <div className="min-h-screen py-12 px-4" style={{ backgroundColor: '#FAF6EF' }}>
      <div className="max-w-7xl mx-auto">

        <div className="mb-10 animate-fade-in-down">
          <p className="text-xs uppercase tracking-widest mb-2 font-medium"
            style={{ fontFamily: "'DM Sans', sans-serif", color: '#C8922A' }}>
            Analysis & Research
          </p>
          <h1 className="text-4xl font-normal mb-2"
            style={{ fontFamily: "'Crimson Pro', Georgia, serif", color: '#0F1F3D', fontStyle: 'italic' }}>
            Market Insights
          </h1>
          <p className="text-lg"
            style={{ fontFamily: "'DM Sans', sans-serif", color: '#3D2B00', opacity: 0.55 }}>
            Analysis, strategies, and market updates from our research team
          </p>
        </div>

        {/* Category filter */}
        <div className="flex flex-wrap gap-3 mb-10 animate-fade-in-up">
          {categories.map((cat) => {
            const isActive = cat === activeCategory;
            const accent = cat === 'All' ? '#C8922A' : (categoryAccent[cat] || '#C8922A');
            return (
              <button key={cat} onClick={() => setActiveCategory(cat)}
                className="px-5 py-2 rounded-full text-sm font-medium transition-all"
                style={{
                  fontFamily: "'DM Sans', sans-serif",
                  backgroundColor: isActive ? accent : '#FFFFFF',
                  color: isActive ? '#FFFFFF' : '#3D2B00',
                  border: `1.5px solid ${isActive ? accent : '#EDE3D0'}`,
                }}>
                {cat}
              </button>
            );
          })}
        </div>

        {/* Articles */}
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
          {filtered.map((article, index) => {
            const accent = categoryAccent[article.category] || '#C8922A';
            return (
              <article key={article.id}
                className="rounded-2xl overflow-hidden border transition-all hover:-translate-y-1 hover:shadow-xl animate-fade-in-up"
                style={{ backgroundColor: '#FFFFFF', borderColor: '#EDE3D0', animationDelay: `${index * 0.08}s` }}>
                <div className="h-48 overflow-hidden">
                  <img src={article.image} alt={article.title}
                    className="w-full h-full object-cover hover:scale-105 transition-transform duration-500" />
                </div>
                <div className="p-6">
                  <span className="text-xs font-semibold px-3 py-1 rounded-full inline-block mb-3"
                    style={{
                      fontFamily: "'DM Sans', sans-serif",
                      backgroundColor: `${accent}18`,
                      color: accent
                    }}>
                    {article.category}
                  </span>
                  <h2 className="text-lg font-semibold mb-3 line-clamp-2 leading-snug cursor-pointer hover:opacity-70 transition-opacity"
                    style={{ fontFamily: "'DM Sans', sans-serif", color: '#0F1F3D' }}>
                    {article.title}
                  </h2>
                  <p className="mb-4 line-clamp-3 leading-relaxed text-base"
                    style={{ fontFamily: "'Crimson Pro', Georgia, serif", color: '#3D2B00', opacity: 0.7 }}>
                    {article.excerpt}
                  </p>
                  <div className="pt-4 border-t space-y-2" style={{ borderColor: '#F0E8D8' }}>
                    <div className="flex items-center justify-between text-xs"
                      style={{ fontFamily: "'DM Sans', sans-serif", color: '#3D2B00', opacity: 0.5 }}>
                      <div className="flex items-center space-x-1.5">
                        <User className="h-3.5 w-3.5" />
                        <span>{article.author}</span>
                      </div>
                      <div className="flex items-center space-x-1.5">
                        <Clock className="h-3.5 w-3.5" />
                        <span>{article.readTime}</span>
                      </div>
                    </div>
                    <div className="flex items-center space-x-1.5 text-xs"
                      style={{ fontFamily: "'DM Sans', sans-serif", color: '#3D2B00', opacity: 0.5 }}>
                      <Calendar className="h-3.5 w-3.5" />
                      <span>{article.date}</span>
                    </div>
                  </div>
                </div>
              </article>
            );
          })}
        </div>

        {/* CTA */}
        <div className="mt-16 rounded-3xl p-12 text-white text-center animate-fade-in-up relative overflow-hidden"
          style={{ background: 'linear-gradient(135deg, #0F1F3D, #1A3366)' }}>
          <div className="absolute top-0 right-0 w-64 h-64 rounded-full blur-3xl opacity-10"
            style={{ backgroundColor: '#C8922A' }} />
          <TrendingUp className="h-14 w-14 mx-auto mb-5 opacity-80" style={{ color: '#E8A020' }} />
          <h2 className="text-3xl font-normal mb-3"
            style={{ fontFamily: "'Crimson Pro', Georgia, serif", fontStyle: 'italic' }}>
            Ready to start trading?
          </h2>
          <p className="text-base mb-8"
            style={{ fontFamily: "'DM Sans', sans-serif", color: '#C8A87A' }}>
            Use our AI platform to find opportunities and execute trades with confidence
          </p>
          <button
            className="px-8 py-4 rounded-xl font-semibold text-lg transition-all hover:-translate-y-1 hover:shadow-2xl"
            style={{
              background: 'linear-gradient(135deg, #C8922A, #E8A020)',
              color: '#FFFFFF',
              fontFamily: "'DM Sans', sans-serif"
            }}>
            Launch Platform
          </button>
        </div>

      </div>
    </div>
  );
}