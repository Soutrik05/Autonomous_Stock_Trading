import type {
  AgentLeaderboardEntry,
  Position,
  Order,
  Decision,
  HeuristicMemory,
  NavHistoryPoint,
  BaselineComparison,
  ActivityEvent,
  PipelineHealthJob,
  BacktestRegimeWindow,
} from '../types';

import {
  MOCK_LEADERBOARD,
  MOCK_POSITIONS,
  MOCK_ORDERS,
  MOCK_DECISIONS,
  MOCK_HEURISTICS,
  MOCK_NAV_HISTORY,
  MOCK_BASELINE_COMPARISON,
  MOCK_ACTIVITY_FEED,
  MOCK_PIPELINE_HEALTH,
  MOCK_BACKTEST_WINDOWS,
} from './mockData';

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

// Helper to determine if mock mode is preferred
let isMockOverride: boolean | null = null;

export function getIsMockMode(): boolean {
  if (isMockOverride !== null) return isMockOverride;
  const stored = localStorage.getItem('stockminds_use_mock_data');
  if (stored !== null) {
    return stored === 'true';
  }
  // Default to mock data so UI is 100% functional before backend is running
  return true;
}

export function setMockMode(enabled: boolean): void {
  isMockOverride = enabled;
  localStorage.setItem('stockminds_use_mock_data', String(enabled));
  window.dispatchEvent(new Event('mock_mode_changed'));
}

async function fetchFromBackend<T>(endpoint: string): Promise<T> {
  const response = await fetch(`${BASE_URL}${endpoint}`);
  if (!response.ok) {
    throw new Error(`API error ${response.status}: ${response.statusText}`);
  }
  return response.json();
}

export const apiService = {
  async getLeaderboard(): Promise<AgentLeaderboardEntry[]> {
    if (getIsMockMode()) return MOCK_LEADERBOARD;
    try {
      return await fetchFromBackend<AgentLeaderboardEntry[]>('/leaderboard');
    } catch {
      return MOCK_LEADERBOARD;
    }
  },

  async getAgentPositions(agentId: string): Promise<Position[]> {
    if (getIsMockMode()) {
      return MOCK_POSITIONS.filter((p) => p.agentId === agentId || agentId === 'all');
    }
    try {
      return await fetchFromBackend<Position[]>(`/agents/${agentId}/positions`);
    } catch {
      return MOCK_POSITIONS.filter((p) => p.agentId === agentId || agentId === 'all');
    }
  },

  async getAgentOrders(agentId: string): Promise<Order[]> {
    if (getIsMockMode()) {
      return MOCK_ORDERS.filter((o) => o.agentId === agentId || agentId === 'all');
    }
    try {
      return await fetchFromBackend<Order[]>(`/agents/${agentId}/orders`);
    } catch {
      return MOCK_ORDERS.filter((o) => o.agentId === agentId || agentId === 'all');
    }
  },

  async getAgentDecisions(agentId: string): Promise<Decision[]> {
    if (getIsMockMode()) {
      return MOCK_DECISIONS.filter((d) => d.agentId === agentId || agentId === 'all');
    }
    try {
      return await fetchFromBackend<Decision[]>(`/agents/${agentId}/decisions`);
    } catch {
      return MOCK_DECISIONS.filter((d) => d.agentId === agentId || agentId === 'all');
    }
  },

  async getAgentNavHistory(): Promise<NavHistoryPoint[]> {
    if (getIsMockMode()) return MOCK_NAV_HISTORY;
    try {
      return await fetchFromBackend<NavHistoryPoint[]>('/agents/nav');
    } catch {
      return MOCK_NAV_HISTORY;
    }
  },

  async getAgentMemory(agentId: string): Promise<HeuristicMemory[]> {
    if (getIsMockMode()) {
      return MOCK_HEURISTICS.filter((h) => h.agentId === agentId || agentId === 'all');
    }
    try {
      return await fetchFromBackend<HeuristicMemory[]>(`/agents/${agentId}/memory`);
    } catch {
      return MOCK_HEURISTICS.filter((h) => h.agentId === agentId || agentId === 'all');
    }
  },

  async getBaselineComparison(): Promise<BaselineComparison> {
    if (getIsMockMode()) return MOCK_BASELINE_COMPARISON;
    try {
      return await fetchFromBackend<BaselineComparison>('/baseline/comparison');
    } catch {
      return MOCK_BASELINE_COMPARISON;
    }
  },

  async getActivityFeed(): Promise<ActivityEvent[]> {
    if (getIsMockMode()) return MOCK_ACTIVITY_FEED;
    try {
      return await fetchFromBackend<ActivityEvent[]>('/activity');
    } catch {
      return MOCK_ACTIVITY_FEED;
    }
  },

  async getPipelineHealth(): Promise<PipelineHealthJob[]> {
    if (getIsMockMode()) return MOCK_PIPELINE_HEALTH;
    try {
      return await fetchFromBackend<PipelineHealthJob[]>('/health');
    } catch {
      return MOCK_PIPELINE_HEALTH;
    }
  },

  async getBacktestWindows(): Promise<BacktestRegimeWindow[]> {
    if (getIsMockMode()) return MOCK_BACKTEST_WINDOWS;
    try {
      return await fetchFromBackend<BacktestRegimeWindow[]>('/backtest/windows');
    } catch {
      return MOCK_BACKTEST_WINDOWS;
    }
  },

  async checkBackendConnection(): Promise<boolean> {
    try {
      const res = await fetch(`${BASE_URL}/health`, { method: 'GET', signal: AbortSignal.timeout(2000) });
      return res.ok;
    } catch {
      return false;
    }
  },
};
