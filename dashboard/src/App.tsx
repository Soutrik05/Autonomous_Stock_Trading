import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import Home from './pages/Home';
import Leaderboard from './pages/Leaderboard';
import Portfolio from './pages/Portfolio';
import Comparison from './pages/Comparison';
import Backtest from './pages/Backtest';
import Pulse from './pages/Pulse';

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Home />} />
          <Route path="leaderboard" element={<Leaderboard />} />
          <Route path="portfolio/:id" element={<Portfolio />} />
          <Route path="portfolio" element={<Navigate to="/portfolio/simons" replace />} />
          <Route path="agents/:id" element={<Portfolio />} />
          <Route path="agents" element={<Navigate to="/portfolio/simons" replace />} />
          <Route path="comparison" element={<Comparison />} />
          <Route path="baseline" element={<Navigate to="/comparison" replace />} />
          <Route path="backtest" element={<Backtest />} />
          <Route path="pulse" element={<Pulse />} />
          <Route path="activity" element={<Navigate to="/pulse" replace />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </Router>
  );
}

export default App;
