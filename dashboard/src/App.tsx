import { lazy, Suspense } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';

// Code splitting via React.lazy to minimize initial bundle size and ensure LCP <= 2.5s
const Home = lazy(() => import('./pages/Home'));
const Leaderboard = lazy(() => import('./pages/Leaderboard'));
const Portfolio = lazy(() => import('./pages/Portfolio'));
const Comparison = lazy(() => import('./pages/Comparison'));
const Backtest = lazy(() => import('./pages/Backtest'));
const Pulse = lazy(() => import('./pages/Pulse'));

// Subtle, low-CLS loading fallback matching the OpenRouter dark glass arena palette
function PageLoadingFallback() {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20 animate-pulse">
      <div className="h-8 w-64 bg-white/10 rounded-lg mb-4" />
      <div className="h-4 w-96 bg-white/5 rounded mb-12" />
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="h-32 bg-white/[0.03] border border-white/10 rounded-xl" />
        <div className="h-32 bg-white/[0.03] border border-white/10 rounded-xl" />
        <div className="h-32 bg-white/[0.03] border border-white/10 rounded-xl" />
      </div>
      <div className="h-96 bg-white/[0.03] border border-white/10 rounded-xl" />
    </div>
  );
}

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route
            index
            element={
              <Suspense fallback={<PageLoadingFallback />}>
                <Home />
              </Suspense>
            }
          />
          <Route
            path="leaderboard"
            element={
              <Suspense fallback={<PageLoadingFallback />}>
                <Leaderboard />
              </Suspense>
            }
          />
          <Route
            path="portfolio/:id"
            element={
              <Suspense fallback={<PageLoadingFallback />}>
                <Portfolio />
              </Suspense>
            }
          />
          <Route path="portfolio" element={<Navigate to="/portfolio/simons" replace />} />
          <Route path="agents/:id" element={<Portfolio />} />
          <Route path="agents" element={<Navigate to="/portfolio/simons" replace />} />
          <Route
            path="comparison"
            element={
              <Suspense fallback={<PageLoadingFallback />}>
                <Comparison />
              </Suspense>
            }
          />
          <Route path="baseline" element={<Navigate to="/comparison" replace />} />
          <Route
            path="backtest"
            element={
              <Suspense fallback={<PageLoadingFallback />}>
                <Backtest />
              </Suspense>
            }
          />
          <Route
            path="pulse"
            element={
              <Suspense fallback={<PageLoadingFallback />}>
                <Pulse />
              </Suspense>
            }
          />
          <Route path="activity" element={<Navigate to="/pulse" replace />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </Router>
  );
}

export default App;
