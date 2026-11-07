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

// Subtle, low-CLS loading fallback matching the archival vellum palette
function PageLoadingFallback() {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 animate-pulse">
      <div className="h-6 w-48 bg-[#DCD7CC] rounded mb-4" />
      <div className="h-4 w-96 bg-[#E7E3D9] rounded mb-12" />
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="h-28 bg-[#FFFFFF] border border-[#DCD7CC] rounded-[3px]" />
        <div className="h-28 bg-[#FFFFFF] border border-[#DCD7CC] rounded-[3px]" />
        <div className="h-28 bg-[#FFFFFF] border border-[#DCD7CC] rounded-[3px]" />
      </div>
      <div className="h-80 bg-[#FFFFFF] border border-[#DCD7CC] rounded-[3px]" />
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
