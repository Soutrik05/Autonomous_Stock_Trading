import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import Leaderboard from './pages/Leaderboard';
import AgentDetail from './pages/AgentDetail';
import BaselineCompare from './pages/BaselineCompare';
import ActivityFeed from './pages/ActivityFeed';
import Backtest from './pages/Backtest';
import Health from './pages/Health';

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Leaderboard />} />
          <Route path="leaderboard" element={<Leaderboard />} />
          <Route path="agents" element={<Navigate to="/agents/simons" replace />} />
          <Route path="agents/:id" element={<AgentDetail />} />
          <Route path="comparison" element={<BaselineCompare />} />
          <Route path="baseline" element={<BaselineCompare />} />
          <Route path="activity" element={<ActivityFeed />} />
          <Route path="backtest" element={<Backtest />} />
          <Route path="health" element={<Health />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </Router>
  );
}

export default App;
