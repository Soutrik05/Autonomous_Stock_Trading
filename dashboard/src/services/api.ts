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
  AgentId,
} from '../types';

import { STRATEGY_THEME } from '../theme/tokens';

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

// Helper to determine if mock mode is preferred (default: false to use real APIs)
let isMockOverride: boolean | null = null;

export function getIsMockMode(): boolean {
  if (isMockOverride !== null) return isMockOverride;
  const stored = localStorage.getItem('stockminds_use_mock_data');
  if (stored !== null) {
    return stored === 'true';
  }
  // Default to real backend API data
  return false;
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

function getHorizonForAgent(id: string): string {
  if (id.includes('simons')) return '1-5d';
  if (id.includes('varsity') || id.includes('core')) return '5-20d';
  if (id.includes('lynch')) return '15-60d';
  if (id.includes('marks')) return '30-90d';
  if (id.includes('jhunjhunwala') || id.includes('rj')) return '90-180d';
  return '5-30d';
}

function normalizeLeaderboard(raw: any[]): AgentLeaderboardEntry[] {
  return raw.map((r) => ({
    id: r.id as AgentId,
    name: r.name,
    philosophy: r.strategy_family || r.philosophy || '',
    horizonDays: r.horizon_days || getHorizonForAgent(r.id),
    navPaise: r.nav_paise ?? r.navPaise ?? 10000000,
    startingCapitalPaise: r.starting_capital_paise ?? r.startingCapitalPaise ?? 10000000,
    returnPct: r.return_pct ?? r.returnPct ?? 0,
    alphaVsBenchmarkPct: r.alpha_vs_benchmark_pct ?? r.alphaVsBenchmarkPct ?? 0,
    sharpeRatio: r.sharpe_ratio ?? r.sharpeRatio ?? 0,
    maxDrawdownPct: r.max_drawdown_pct ?? r.maxDrawdownPct ?? 0,
    winRatePct: r.win_rate_pct ?? r.winRatePct ?? 0,
    faithfulnessRatePct: r.faithfulness_rate_pct ?? r.faithfulnessRatePct ?? 100,
    totalTrades: r.total_trades ?? r.totalTrades ?? 0,
    closedTrades: r.closed_trades ?? r.closedTrades ?? 0,
    isProvisional: r.is_provisional ?? r.isProvisional ?? true,
    activePositionsCount: r.active_positions_count ?? r.activePositionsCount ?? 0,
    lastActiveDate: r.last_active_date || '2026-10-29',
  }));
}

function normalizePosition(r: any): Position {
  return {
    id: r.id,
    agentId: (r.agent_id || r.agentId) as AgentId,
    symbol: r.symbol || r.ticker || '',
    companyName: r.company_name || r.companyName || r.symbol || r.ticker || '',
    sector: r.sector || 'Equities',
    quantity: r.quantity ?? r.shares ?? 0,
    entryPricePaise: r.entry_price_paise ?? r.entryPricePaise ?? 0,
    currentPricePaise: r.current_price_paise ?? r.currentPricePaise ?? r.entry_price_paise ?? 0,
    exitPricePaise: r.exit_price_paise ?? r.exitPricePaise,
    stopLossPaise: r.stop_loss_paise ?? r.stopLossPaise ?? r.stop_paise ?? 0,
    targetPricePaise: r.target_price_paise ?? r.targetPricePaise ?? r.target_paise,
    status: r.status,
    unrealizedPnlPaise: r.unrealized_pnl_paise ?? r.unrealizedPnlPaise ?? 0,
    unrealizedPnlPct: r.unrealized_pnl_pct ?? r.unrealizedPnlPct ?? 0,
    realizedPnlPaise: r.realized_pnl_paise ?? r.realizedPnlPaise,
    realizedPnlPct: r.realized_pnl_pct ?? r.realizedPnlPct,
    openedAt: r.opened_at || r.openedAt || '',
    closedAt: r.closed_at || r.closedAt,
    holdDays: r.hold_days ?? r.holdDays ?? 0,
    forensicTag: r.forensic_tag || r.forensics_type || r.forensicTag || 'NONE',
    isFrozen: Boolean(r.is_frozen ?? r.isFrozen),
    thesisSummary: r.thesis_summary || r.thesisSummary || r.entry_reasoning || '',
  };
}

function normalizeOrder(r: any): Order {
  return {
    id: r.id,
    agentId: (r.agent_id || r.agentId) as AgentId,
    symbol: r.symbol || r.ticker || '',
    side: r.side,
    orderType: r.order_type || r.orderType || 'LIMIT',
    quantity: r.quantity ?? r.shares ?? 0,
    limitPricePaise: r.limit_price_paise ?? r.entry_high_paise ?? r.limitPricePaise ?? 0,
    filledPricePaise: r.filled_price_paise ?? r.filledPricePaise,
    status: r.status,
    rejectionReason: r.rejection_reason || r.rejectionReason,
    submittedAt: r.submitted_at || r.submittedAt || '',
    filledAt: r.filled_at || r.filledAt,
    statutoryChargesPaise: r.statutory_charges_paise ?? r.statutoryChargesPaise ?? 0,
    slippagePaise: r.slippage_paise ?? r.slippagePaise ?? 0,
  };
}

function normalizeDecision(r: any): Decision {
  return {
    id: r.id,
    agentId: (r.agent_id || r.agentId) as AgentId,
    symbol: r.symbol || r.ticker || '',
    decisionDate: r.decision_date || r.run_date || r.decisionDate || '',
    action: r.action,
    rationale: r.rationale || r.reasoning || '',
    preMortemRisk: r.pre_mortem_risk || r.preMortemRisk || undefined,
    faithfulnessScore: r.faithfulness_score ?? r.faithfulnessScore ?? 1.0,
    sizingFidelityScore: r.sizing_fidelity_score ?? r.sizingFidelityScore ?? 1.0,
    candidateRank: r.candidate_rank ?? r.candidateRank ?? 1,
    stageReached: r.stage_reached || r.stageReached || 'FINAL',
    allocatedPaise: r.allocated_paise ?? r.allocatedPaise,
    citedMetrics: Array.isArray(r.cited_metrics)
      ? r.cited_metrics.map((m: any) => ({
          name: typeof m === 'string' ? m : m.name,
          citedValue: m.cited_value ?? m.citedValue ?? 0,
          actualSnapshotValue: m.actual_snapshot_value ?? m.actualSnapshotValue ?? 0,
          tolerance: m.tolerance ?? 'EXACT',
          isFaithful: m.is_faithful ?? m.isFaithful ?? true,
        }))
      : [],
  };
}

function normalizeNavHistory(raw: any[]): NavHistoryPoint[] {
  if (!Array.isArray(raw)) return MOCK_NAV_HISTORY;
  return raw.map((r) => {
    const vals = r.values || {};
    return {
      date: r.date || '',
      simons: vals.simons ?? 10000000,
      baselineSimons: vals['baseline-simons-rules'] ?? 10000000,
      lynch: vals.lynch ?? 10000000,
      baselineLynch: vals['baseline-lynch-rules'] ?? 10000000,
      marks: vals.marks ?? 10000000,
      baselineMarks: vals['baseline-marks-rules'] ?? 10000000,
      jhunjhunwala: vals.jhunjhunwala ?? 10000000,
      baselineRj: vals['baseline-rj-rules'] ?? 10000000,
      stockmindsCore: vals.varsity ?? vals['stockminds-core'] ?? 10000000,
      baselineVarsity: vals['baseline-varsity-rules'] ?? 10000000,
      nifty500: vals.nifty500 ?? 10000000,
    };
  });
}

function normalizeHeuristic(r: any): HeuristicMemory {
  return {
    id: r.id,
    agentId: (r.agent_id || r.agentId) as AgentId,
    kind: r.kind,
    ruleDescription: r.rule_text || r.ruleDescription || r.heuristic_text || '',
    triggerPredicate: r.context || r.triggerPredicate || '',
    status: (r.status ? r.status.toUpperCase() : 'ACTIVE') as any,
    confidenceScore: r.confidence ?? r.confidenceScore ?? 0.8,
    timesApplied: r.applications ?? r.timesApplied ?? 0,
    successRatePct: r.recent_success_rate ?? r.successRatePct ?? 0,
    createdAt: r.created_at || r.createdAt || '',
    lastTestedAt: r.updated_at || r.lastTestedAt || '',
  };
}

function normalizeBaselineComparison(raw: any): BaselineComparison {
  const llm = raw.llm_agent || raw.llmSimons || {};
  const rules = raw.rules_agent || raw.rulesSimons || {};
  const nifty = raw.nifty500 || {};
  const horizons = (raw.horizon_returns || raw.horizonReturns || []).map((h: any) => ({
    horizonDays: h.horizon_days ?? h.horizonDays ?? 1,
    llmSimonsBuyAvgPct: h.llm_buy_avg_pct ?? h.llmSimonsBuyAvgPct ?? 0,
    llmSimonsHoldAvgPct: h.llm_hold_avg_pct ?? h.llmSimonsHoldAvgPct ?? 0,
    rulesSimonsBuyAvgPct: h.rules_buy_avg_pct ?? h.rulesSimonsBuyAvgPct ?? 0,
    nifty500AvgPct: h.nifty500_avg_pct ?? h.nifty500AvgPct ?? 0,
    selectionAlphaPct: h.selection_alpha_pct ?? h.selectionAlphaPct ?? 0,
  }));

  return {
    llmSimons: {
      navPaise: llm.nav_paise ?? llm.navPaise ?? 9986622,
      returnPct: llm.return_pct ?? llm.returnPct ?? 0,
      sharpe: llm.sharpe_ratio ?? llm.sharpe ?? 0,
      maxDrawdownPct: llm.max_drawdown_pct ?? llm.maxDrawdownPct ?? 0,
      winRatePct: llm.win_rate_pct ?? llm.winRatePct ?? 0,
      faithfulnessRatePct: llm.faithfulness_rate_pct ?? llm.faithfulnessRatePct ?? 100,
      trades: llm.trades ?? 0,
    },
    rulesSimons: {
      navPaise: rules.nav_paise ?? rules.navPaise ?? 9998310,
      returnPct: rules.return_pct ?? rules.returnPct ?? 0,
      sharpe: rules.sharpe_ratio ?? rules.sharpe ?? 0,
      maxDrawdownPct: rules.max_drawdown_pct ?? rules.maxDrawdownPct ?? 0,
      winRatePct: rules.win_rate_pct ?? rules.winRatePct ?? 0,
      trades: rules.trades ?? 0,
    },
    nifty500: {
      benchmarkNavPaise: nifty.benchmark_nav_paise ?? nifty.benchmarkNavPaise ?? 10000000,
      returnPct: nifty.return_pct ?? nifty.returnPct ?? 0,
      maxDrawdownPct: nifty.max_drawdown_pct ?? nifty.maxDrawdownPct ?? 0,
    },
    candidateSelectionAlpha: raw.deltas?.excess_alpha_pct ?? raw.candidateSelectionAlpha ?? 0,
    horizonReturns: horizons,
  };
}

function normalizeActivity(r: any): ActivityEvent {
  return {
    id: String(r.id),
    timestamp: r.timestamp || '',
    eventType: r.event_type || r.eventType || 'ORDER_SUBMITTED',
    agentId: (r.agent_id || r.agentId) as AgentId,
    symbol: r.symbol,
    message: r.message || '',
    severity: (r.severity || 'INFO') as any,
    details: r.details,
  };
}

function normalizeHealth(r: any): PipelineHealthJob {
  return {
    jobName: r.job_name || r.jobName || '',
    cadence: r.cadence || '',
    status: (r.status || 'SUCCESS') as any,
    lastRunAt: r.last_run_at || r.lastRunAt || '',
    durationSec: r.duration_sec ?? r.durationSec ?? 0,
    recordsProcessed: r.records_processed ?? r.recordsProcessed,
    errorMessage: r.error_message ?? r.errorMessage,
  };
}

export const apiService = {
  async getLeaderboard(): Promise<AgentLeaderboardEntry[]> {
    if (getIsMockMode()) return MOCK_LEADERBOARD;
    try {
      const data = await fetchFromBackend<any[]>('/leaderboard');
      return normalizeLeaderboard(data);
    } catch {
      return MOCK_LEADERBOARD;
    }
  },

  async getAgentPositions(agentId: string): Promise<Position[]> {
    if (getIsMockMode()) {
      return MOCK_POSITIONS.filter((p) => p.agentId === agentId || agentId === 'all');
    }
    try {
      const data = await fetchFromBackend<any[]>(`/agents/${agentId}/positions`);
      return data.map(normalizePosition);
    } catch {
      return MOCK_POSITIONS.filter((p) => p.agentId === agentId || agentId === 'all');
    }
  },

  async getAgentOrders(agentId: string): Promise<Order[]> {
    if (getIsMockMode()) {
      return MOCK_ORDERS.filter((o) => o.agentId === agentId || agentId === 'all');
    }
    try {
      const data = await fetchFromBackend<any[]>(`/agents/${agentId}/orders`);
      return data.map(normalizeOrder);
    } catch {
      return MOCK_ORDERS.filter((o) => o.agentId === agentId || agentId === 'all');
    }
  },

  async getAgentDecisions(agentId: string): Promise<Decision[]> {
    if (getIsMockMode()) {
      return MOCK_DECISIONS.filter((d) => d.agentId === agentId || agentId === 'all');
    }
    try {
      const data = await fetchFromBackend<any[]>(`/agents/${agentId}/decisions`);
      const normalized = data.map(normalizeDecision);
      // Prioritize decisions with preMortemRisk or BUY action so rich decisions display first
      normalized.sort((a, b) => {
        const aScore = (a.preMortemRisk ? 2 : 0) + (a.action === 'BUY' ? 1 : 0);
        const bScore = (b.preMortemRisk ? 2 : 0) + (b.action === 'BUY' ? 1 : 0);
        return bScore - aScore;
      });
      return normalized;
    } catch {
      return MOCK_DECISIONS.filter((d) => d.agentId === agentId || agentId === 'all');
    }
  },

  async getAgentNavHistory(): Promise<NavHistoryPoint[]> {
    if (getIsMockMode()) return MOCK_NAV_HISTORY;
    try {
      const data = await fetchFromBackend<any[]>('/agents/nav');
      return normalizeNavHistory(data);
    } catch {
      return MOCK_NAV_HISTORY;
    }
  },

  async getAgentMemory(agentId: string): Promise<HeuristicMemory[]> {
    if (getIsMockMode()) {
      return MOCK_HEURISTICS.filter((h) => h.agentId === agentId || agentId === 'all');
    }
    try {
      const data = await fetchFromBackend<any[]>(`/agents/${agentId}/memory`);
      return data.map(normalizeHeuristic);
    } catch {
      return MOCK_HEURISTICS.filter((h) => h.agentId === agentId || agentId === 'all');
    }
  },

  async getBaselineComparison(): Promise<BaselineComparison> {
    if (getIsMockMode()) return MOCK_BASELINE_COMPARISON;
    try {
      const data = await fetchFromBackend<any>('/baseline/comparison');
      return normalizeBaselineComparison(data);
    } catch {
      return MOCK_BASELINE_COMPARISON;
    }
  },

  async getActivityFeed(): Promise<ActivityEvent[]> {
    if (getIsMockMode()) return MOCK_ACTIVITY_FEED;
    try {
      const data = await fetchFromBackend<any>('/activity');
      const rawEvents = Array.isArray(data) ? data : data.events || [];
      return rawEvents.map(normalizeActivity);
    } catch {
      return MOCK_ACTIVITY_FEED;
    }
  },

  async getPipelineHealth(): Promise<PipelineHealthJob[]> {
    if (getIsMockMode()) return MOCK_PIPELINE_HEALTH;
    try {
      const data = await fetchFromBackend<any>('/health');
      const rawJobs = Array.isArray(data) ? data : data.jobs || [];
      return rawJobs.map(normalizeHealth);
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

  async getRunLeaderboard(windowId: string): Promise<AgentLeaderboardEntry[]> {
    if (getIsMockMode()) {
      return getMockRunLeaderboard(windowId);
    }
    try {
      const data = await fetchFromBackend<any>(`/backtest/runs/${windowId}/leaderboard`);
      const rawList = data?.leaderboard || [];
      if (!Array.isArray(rawList) || rawList.length === 0) {
        return getMockRunLeaderboard(windowId);
      }
      return rawList.map((r: any) => {
        const canonicalId = r.agent_id === 'varsity' ? 'stockminds-core' : r.agent_id;
        const theme = STRATEGY_THEME[canonicalId] || STRATEGY_THEME[r.agent_id];
        return {
          id: r.agent_id as AgentId,
          name: theme?.name || r.agent_id,
          philosophy: theme?.family || '',
          horizonDays: getHorizonForAgent(r.agent_id),
          navPaise: r.current_nav_paise ?? 50000000,
          startingCapitalPaise: r.initial_nav_paise ?? 50000000,
          returnPct: r.total_return_pct ?? 0,
          alphaVsBenchmarkPct: r.alpha_pct ?? 0,
          sharpeRatio: r.sharpe_ratio ?? 0,
          maxDrawdownPct: Math.abs(r.max_drawdown_pct ?? 0),
          winRatePct: r.win_rate_pct ?? 0,
          faithfulnessRatePct: r.philosophy_adherence_pct ?? (r.avg_faithfulness ? Math.round(r.avg_faithfulness * 100) : 100),
          totalTrades: r.total_closed_trades ?? 0,
          closedTrades: r.total_closed_trades ?? 0,
          isProvisional: r.is_provisional ?? (r.total_closed_trades < 30),
          activePositionsCount: 3,
          lastActiveDate: '2025-11-21',
        };
      });
    } catch {
      return getMockRunLeaderboard(windowId);
    }
  },

  async getRunNavHistory(windowId: string): Promise<NavHistoryPoint[]> {
    if (getIsMockMode()) {
      return getMockRunNavHistory(windowId);
    }
    try {
      const data = await fetchFromBackend<any>(`/backtest/runs/${windowId}/nav`);
      const rawSeries = data?.nav_series || [];
      if (!Array.isArray(rawSeries) || rawSeries.length === 0) {
        return getMockRunNavHistory(windowId);
      }
      const first = rawSeries[0];
      const startingCashPaise = first?.simons || 50000000;
      const startingCashRupees = startingCashPaise / 100;
      const baseNifty = first?.nifty500 || 1;

      return rawSeries.map((r: any) => {
        const niftyRatio = baseNifty > 0 ? (r.nifty500 || baseNifty) / baseNifty : 1;
        const niftyScaledRupees = Math.round(startingCashRupees * niftyRatio);

        return {
          date: r.date,
          simons: Math.round((r.simons ?? startingCashPaise) / 100),
          baselineSimons: Math.round((r['baseline-simons-rules'] ?? startingCashPaise) / 100),
          lynch: Math.round((r.lynch ?? startingCashPaise) / 100),
          baselineLynch: Math.round((r['baseline-lynch-rules'] ?? startingCashPaise) / 100),
          marks: Math.round((r.marks ?? startingCashPaise) / 100),
          baselineMarks: Math.round((r['baseline-marks-rules'] ?? startingCashPaise) / 100),
          jhunjhunwala: Math.round((r.jhunjhunwala ?? startingCashPaise) / 100),
          baselineRj: Math.round((r['baseline-rj-rules'] ?? startingCashPaise) / 100),
          stockmindsCore: Math.round((r.varsity ?? r['stockminds-core'] ?? startingCashPaise) / 100),
          baselineVarsity: Math.round((r['baseline-varsity-rules'] ?? startingCashPaise) / 100),
          nifty500: niftyScaledRupees,
        };
      });
    } catch {
      return getMockRunNavHistory(windowId);
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

function getMockRunLeaderboard(windowId: string): AgentLeaderboardEntry[] {
  const seed = 50000000; // ₹5,00,000 in paise
  if (windowId.includes('w1')) {
    return [
      { id: 'baseline-marks-rules', name: 'Marks (Rules Baseline)', philosophy: 'Contrarian Value', horizonDays: '30–90 days', navPaise: 61315000, startingCapitalPaise: seed, returnPct: 22.63, alphaVsBenchmarkPct: 2.74, sharpeRatio: 0.85, maxDrawdownPct: 12.1, winRatePct: 64.0, faithfulnessRatePct: 100.0, totalTrades: 42, closedTrades: 38, isProvisional: false, activePositionsCount: 4, lastActiveDate: '2025-11-21' },
      { id: 'marks', name: 'Howard Marks (LLM)', philosophy: 'Contrarian Value', horizonDays: '30–90 days', navPaise: 55020000, startingCapitalPaise: seed, returnPct: 10.04, alphaVsBenchmarkPct: -9.85, sharpeRatio: 0.42, maxDrawdownPct: 14.8, winRatePct: 58.0, faithfulnessRatePct: 96.5, totalTrades: 35, closedTrades: 31, isProvisional: false, activePositionsCount: 3, lastActiveDate: '2025-11-21' },
      { id: 'baseline-varsity-rules', name: 'Varsity (Rules Baseline)', philosophy: 'Dual Confluence', horizonDays: '20–60 days', navPaise: 54615000, startingCapitalPaise: seed, returnPct: 9.23, alphaVsBenchmarkPct: -10.66, sharpeRatio: 0.35, maxDrawdownPct: 16.2, winRatePct: 54.0, faithfulnessRatePct: 100.0, totalTrades: 48, closedTrades: 42, isProvisional: false, activePositionsCount: 4, lastActiveDate: '2025-11-21' },
      { id: 'baseline-lynch-rules', name: 'Lynch (Rules Baseline)', philosophy: 'GARP', horizonDays: '60–120 days', navPaise: 52175000, startingCapitalPaise: seed, returnPct: 4.35, alphaVsBenchmarkPct: -15.54, sharpeRatio: 0.11, maxDrawdownPct: 15.1, winRatePct: 61.5, faithfulnessRatePct: 100.0, totalTrades: 39, closedTrades: 35, isProvisional: false, activePositionsCount: 3, lastActiveDate: '2025-11-21' },
      { id: 'stockminds-core', name: 'StockMinds Core (LLM)', philosophy: 'Dual Confluence', horizonDays: '20–60 days', navPaise: 51830000, startingCapitalPaise: seed, returnPct: 3.66, alphaVsBenchmarkPct: -16.23, sharpeRatio: 0.12, maxDrawdownPct: 17.5, winRatePct: 50.0, faithfulnessRatePct: 98.4, totalTrades: 44, closedTrades: 40, isProvisional: false, activePositionsCount: 4, lastActiveDate: '2025-11-21' },
      { id: 'baseline-simons-rules', name: 'Simons (Rules Baseline)', philosophy: 'Quant Momentum', horizonDays: '5–15 days', navPaise: 49030000, startingCapitalPaise: seed, returnPct: -1.94, alphaVsBenchmarkPct: -21.83, sharpeRatio: -0.08, maxDrawdownPct: 13.9, winRatePct: 48.0, faithfulnessRatePct: 100.0, totalTrades: 62, closedTrades: 58, isProvisional: false, activePositionsCount: 4, lastActiveDate: '2025-11-21' },
      { id: 'simons', name: 'Jim Simons (LLM)', philosophy: 'Quant Momentum', horizonDays: '5–15 days', navPaise: 48235000, startingCapitalPaise: seed, returnPct: -3.53, alphaVsBenchmarkPct: -23.42, sharpeRatio: -0.22, maxDrawdownPct: 12.5, winRatePct: 52.0, faithfulnessRatePct: 98.0, totalTrades: 56, closedTrades: 51, isProvisional: false, activePositionsCount: 4, lastActiveDate: '2025-11-21' },
      { id: 'lynch', name: 'Peter Lynch (LLM)', philosophy: 'GARP', horizonDays: '60–120 days', navPaise: 47000000, startingCapitalPaise: seed, returnPct: -6.00, alphaVsBenchmarkPct: -25.89, sharpeRatio: -0.32, maxDrawdownPct: 18.2, winRatePct: 44.0, faithfulnessRatePct: 96.0, totalTrades: 32, closedTrades: 28, isProvisional: true, activePositionsCount: 3, lastActiveDate: '2025-11-21' },
      { id: 'baseline-rj-rules', name: 'Jhunjhunwala (Rules Baseline)', philosophy: 'Secular Growth', horizonDays: '90–180 days', navPaise: 46515000, startingCapitalPaise: seed, returnPct: -6.97, alphaVsBenchmarkPct: -26.86, sharpeRatio: -0.41, maxDrawdownPct: 19.5, winRatePct: 42.0, faithfulnessRatePct: 100.0, totalTrades: 25, closedTrades: 20, isProvisional: true, activePositionsCount: 4, lastActiveDate: '2025-11-21' },
      { id: 'jhunjhunwala', name: 'Rakesh Jhunjhunwala (LLM)', philosophy: 'Secular Growth', horizonDays: '90–180 days', navPaise: 44755000, startingCapitalPaise: seed, returnPct: -10.49, alphaVsBenchmarkPct: -30.38, sharpeRatio: -0.55, maxDrawdownPct: 21.0, winRatePct: 38.0, faithfulnessRatePct: 95.0, totalTrades: 22, closedTrades: 18, isProvisional: true, activePositionsCount: 4, lastActiveDate: '2025-11-21' },
    ];
  }
  if (windowId.includes('s1')) {
    return [
      { id: 'baseline-marks-rules', name: 'Marks (Rules Baseline)', philosophy: 'Contrarian Value', horizonDays: '30–90 days', navPaise: 52435000, startingCapitalPaise: seed, returnPct: 4.87, alphaVsBenchmarkPct: 8.82, sharpeRatio: 1.25, maxDrawdownPct: 3.2, winRatePct: 62.0, faithfulnessRatePct: 100.0, totalTrades: 18, closedTrades: 16, isProvisional: true, activePositionsCount: 3, lastActiveDate: '2025-06-30' },
      { id: 'marks', name: 'Howard Marks (LLM)', philosophy: 'Contrarian Value', horizonDays: '30–90 days', navPaise: 51470000, startingCapitalPaise: seed, returnPct: 2.94, alphaVsBenchmarkPct: 6.89, sharpeRatio: 0.95, maxDrawdownPct: 3.8, winRatePct: 58.0, faithfulnessRatePct: 97.2, totalTrades: 15, closedTrades: 13, isProvisional: true, activePositionsCount: 2, lastActiveDate: '2025-06-30' },
      { id: 'baseline-lynch-rules', name: 'Lynch (Rules Baseline)', philosophy: 'GARP', horizonDays: '60–120 days', navPaise: 50980000, startingCapitalPaise: seed, returnPct: 1.96, alphaVsBenchmarkPct: 5.91, sharpeRatio: 0.75, maxDrawdownPct: 4.1, winRatePct: 55.0, faithfulnessRatePct: 100.0, totalTrades: 14, closedTrades: 12, isProvisional: true, activePositionsCount: 3, lastActiveDate: '2025-06-30' },
      { id: 'stockminds-core', name: 'StockMinds Core (LLM)', philosophy: 'Dual Confluence', horizonDays: '20–60 days', navPaise: 50765000, startingCapitalPaise: seed, returnPct: 1.53, alphaVsBenchmarkPct: 5.48, sharpeRatio: 0.65, maxDrawdownPct: 4.5, winRatePct: 52.0, faithfulnessRatePct: 99.0, totalTrades: 20, closedTrades: 18, isProvisional: true, activePositionsCount: 4, lastActiveDate: '2025-06-30' },
      { id: 'baseline-varsity-rules', name: 'Varsity (Rules Baseline)', philosophy: 'Dual Confluence', horizonDays: '20–60 days', navPaise: 50285000, startingCapitalPaise: seed, returnPct: 0.57, alphaVsBenchmarkPct: 4.52, sharpeRatio: 0.45, maxDrawdownPct: 4.8, winRatePct: 50.0, faithfulnessRatePct: 100.0, totalTrades: 21, closedTrades: 19, isProvisional: true, activePositionsCount: 4, lastActiveDate: '2025-06-30' },
      { id: 'baseline-simons-rules', name: 'Simons (Rules Baseline)', philosophy: 'Quant Momentum', horizonDays: '5–15 days', navPaise: 49825000, startingCapitalPaise: seed, returnPct: -0.35, alphaVsBenchmarkPct: 3.60, sharpeRatio: 0.25, maxDrawdownPct: 4.9, winRatePct: 48.0, faithfulnessRatePct: 100.0, totalTrades: 28, closedTrades: 26, isProvisional: true, activePositionsCount: 4, lastActiveDate: '2025-06-30' },
      { id: 'simons', name: 'Jim Simons (LLM)', philosophy: 'Quant Momentum', horizonDays: '5–15 days', navPaise: 49340000, startingCapitalPaise: seed, returnPct: -1.32, alphaVsBenchmarkPct: 2.63, sharpeRatio: 0.15, maxDrawdownPct: 5.2, winRatePct: 46.0, faithfulnessRatePct: 98.2, totalTrades: 26, closedTrades: 24, isProvisional: true, activePositionsCount: 4, lastActiveDate: '2025-06-30' },
      { id: 'jhunjhunwala', name: 'Rakesh Jhunjhunwala (LLM)', philosophy: 'Secular Growth', horizonDays: '90–180 days', navPaise: 49325000, startingCapitalPaise: seed, returnPct: -1.35, alphaVsBenchmarkPct: 2.60, sharpeRatio: 0.12, maxDrawdownPct: 5.5, winRatePct: 45.0, faithfulnessRatePct: 96.0, totalTrades: 10, closedTrades: 8, isProvisional: true, activePositionsCount: 3, lastActiveDate: '2025-06-30' },
      { id: 'baseline-rj-rules', name: 'Jhunjhunwala (Rules Baseline)', philosophy: 'Secular Growth', horizonDays: '90–180 days', navPaise: 48125000, startingCapitalPaise: seed, returnPct: -3.75, alphaVsBenchmarkPct: 0.20, sharpeRatio: -0.10, maxDrawdownPct: 6.8, winRatePct: 42.0, faithfulnessRatePct: 100.0, totalTrades: 11, closedTrades: 9, isProvisional: true, activePositionsCount: 3, lastActiveDate: '2025-06-30' },
      { id: 'lynch', name: 'Peter Lynch (LLM)', philosophy: 'GARP', horizonDays: '60–120 days', navPaise: 47125000, startingCapitalPaise: seed, returnPct: -5.75, alphaVsBenchmarkPct: -1.80, sharpeRatio: -0.35, maxDrawdownPct: 7.2, winRatePct: 38.0, faithfulnessRatePct: 96.5, totalTrades: 12, closedTrades: 10, isProvisional: true, activePositionsCount: 3, lastActiveDate: '2025-06-30' },
    ];
  }
  // Default to W2 (High Vol Correction & Recovery Vetted Benchmark)
  return [
    { id: 'stockminds-core', name: 'StockMinds Core (LLM)', philosophy: 'Dual Confluence', horizonDays: '5–20 days', navPaise: 52885000, startingCapitalPaise: seed, returnPct: 5.77, alphaVsBenchmarkPct: 5.41, sharpeRatio: 0.26, maxDrawdownPct: 8.5, winRatePct: 43.5, faithfulnessRatePct: 90.9, totalTrades: 92, closedTrades: 92, isProvisional: false, activePositionsCount: 4, lastActiveDate: '2026-10-29' },
    { id: 'baseline-lynch-rules', name: 'Lynch (Rules Baseline)', philosophy: 'GARP', horizonDays: '15–60 days', navPaise: 50200000, startingCapitalPaise: seed, returnPct: 0.40, alphaVsBenchmarkPct: 0.04, sharpeRatio: -0.17, maxDrawdownPct: 14.57, winRatePct: 42.1, faithfulnessRatePct: 94.3, totalTrades: 38, closedTrades: 38, isProvisional: false, activePositionsCount: 3, lastActiveDate: '2026-10-29' },
    { id: 'baseline-varsity-rules', name: 'Varsity (Rules Baseline)', philosophy: 'Dual Confluence', horizonDays: '5–20 days', navPaise: 49740000, startingCapitalPaise: seed, returnPct: -0.52, alphaVsBenchmarkPct: -0.88, sharpeRatio: -0.29, maxDrawdownPct: 13.32, winRatePct: 35.3, faithfulnessRatePct: 96.3, totalTrades: 85, closedTrades: 85, isProvisional: false, activePositionsCount: 4, lastActiveDate: '2026-10-29' },
    { id: 'simons', name: 'Jim Simons (LLM)', philosophy: 'Quant Momentum', horizonDays: '1–10 days', navPaise: 48980000, startingCapitalPaise: seed, returnPct: -2.04, alphaVsBenchmarkPct: -2.40, sharpeRatio: -1.69, maxDrawdownPct: 3.65, winRatePct: 39.1, faithfulnessRatePct: 99.5, totalTrades: 161, closedTrades: 161, isProvisional: false, activePositionsCount: 4, lastActiveDate: '2026-10-29' },
    { id: 'lynch', name: 'Peter Lynch (LLM)', philosophy: 'GARP', horizonDays: '15–60 days', navPaise: 48520000, startingCapitalPaise: seed, returnPct: -2.96, alphaVsBenchmarkPct: -3.32, sharpeRatio: -0.73, maxDrawdownPct: 8.20, winRatePct: 44.4, faithfulnessRatePct: 94.7, totalTrades: 27, closedTrades: 27, isProvisional: true, activePositionsCount: 3, lastActiveDate: '2026-10-29' },
    { id: 'marks', name: 'Howard Marks (LLM)', philosophy: 'Contrarian Value', horizonDays: '30–90 days', navPaise: 48385000, startingCapitalPaise: seed, returnPct: -3.23, alphaVsBenchmarkPct: -3.59, sharpeRatio: -1.16, maxDrawdownPct: 6.61, winRatePct: 37.0, faithfulnessRatePct: 92.8, totalTrades: 46, closedTrades: 46, isProvisional: false, activePositionsCount: 2, lastActiveDate: '2026-10-29' },
    { id: 'baseline-simons-rules', name: 'Simons (Rules Baseline)', philosophy: 'Quant Momentum', horizonDays: '1–10 days', navPaise: 46850000, startingCapitalPaise: seed, returnPct: -6.30, alphaVsBenchmarkPct: -6.66, sharpeRatio: -2.81, maxDrawdownPct: 6.38, winRatePct: 33.3, faithfulnessRatePct: 99.6, totalTrades: 57, closedTrades: 57, isProvisional: false, activePositionsCount: 4, lastActiveDate: '2026-10-29' },
    { id: 'baseline-marks-rules', name: 'Marks (Rules Baseline)', philosophy: 'Contrarian Value', horizonDays: '30–90 days', navPaise: 46410000, startingCapitalPaise: seed, returnPct: -7.18, alphaVsBenchmarkPct: -7.54, sharpeRatio: -0.95, maxDrawdownPct: 14.77, winRatePct: 37.7, faithfulnessRatePct: 94.4, totalTrades: 53, closedTrades: 53, isProvisional: false, activePositionsCount: 2, lastActiveDate: '2026-10-29' },
    { id: 'baseline-rj-rules', name: 'Jhunjhunwala (Rules Baseline)', philosophy: 'Secular Growth', horizonDays: '90–180 days', navPaise: 43745000, startingCapitalPaise: seed, returnPct: -12.51, alphaVsBenchmarkPct: -12.87, sharpeRatio: -1.27, maxDrawdownPct: 15.03, winRatePct: 50.0, faithfulnessRatePct: 93.2, totalTrades: 34, closedTrades: 34, isProvisional: false, activePositionsCount: 4, lastActiveDate: '2026-10-29' },
    { id: 'jhunjhunwala', name: 'Rakesh Jhunjhunwala (LLM)', philosophy: 'Secular Growth', horizonDays: '90–180 days', navPaise: 43260000, startingCapitalPaise: seed, returnPct: -13.48, alphaVsBenchmarkPct: -13.84, sharpeRatio: -1.68, maxDrawdownPct: 15.88, winRatePct: 42.6, faithfulnessRatePct: 86.9, totalTrades: 47, closedTrades: 47, isProvisional: false, activePositionsCount: 4, lastActiveDate: '2026-10-29' },
  ];
}

function getMockRunNavHistory(windowId: string): NavHistoryPoint[] {
  const seed = 500000;
  if (windowId.includes('w1')) {
    return [
      { date: '2025-02-28', simons: seed, baselineSimons: seed, lynch: seed, baselineLynch: seed, marks: seed, baselineMarks: seed, jhunjhunwala: seed, baselineRj: seed, stockmindsCore: seed, baselineVarsity: seed, nifty500: seed },
      { date: '2025-05-15', simons: 495000, baselineSimons: 498000, lynch: 485000, baselineLynch: 512000, marks: 524000, baselineMarks: 556000, jhunjhunwala: 478000, baselineRj: 485000, stockmindsCore: 512000, baselineVarsity: 528000, nifty500: 545000 },
      { date: '2025-08-30', simons: 489000, baselineSimons: 493000, lynch: 476000, baselineLynch: 518000, marks: 538000, baselineMarks: 589000, jhunjhunwala: 462000, baselineRj: 476000, stockmindsCore: 516000, baselineVarsity: 539000, nifty500: 578000 },
      { date: '2025-11-21', simons: 482350, baselineSimons: 490300, lynch: 470000, baselineLynch: 521750, marks: 550200, baselineMarks: 613150, jhunjhunwala: 447550, baselineRj: 465150, stockmindsCore: 518300, baselineVarsity: 546150, nifty500: 599450 },
    ];
  }
  if (windowId.includes('s1')) {
    return [
      { date: '2025-05-02', simons: seed, baselineSimons: seed, lynch: seed, baselineLynch: seed, marks: seed, baselineMarks: seed, jhunjhunwala: seed, baselineRj: seed, stockmindsCore: seed, baselineVarsity: seed, nifty500: seed },
      { date: '2025-05-28', simons: 498000, baselineSimons: 499500, lynch: 485000, baselineLynch: 504000, marks: 508000, baselineMarks: 514000, jhunjhunwala: 497000, baselineRj: 492000, stockmindsCore: 504000, baselineVarsity: 501500, nifty500: 492000 },
      { date: '2025-06-30', simons: 493400, baselineSimons: 498250, lynch: 471250, baselineLynch: 509800, marks: 514700, baselineMarks: 524350, jhunjhunwala: 493250, baselineRj: 481250, stockmindsCore: 507650, baselineVarsity: 502850, nifty500: 480250 },
    ];
  }
  return [
    { date: '2025-10-01', simons: seed, baselineSimons: seed, lynch: seed, baselineLynch: seed, marks: seed, baselineMarks: seed, jhunjhunwala: seed, baselineRj: seed, stockmindsCore: seed, baselineVarsity: seed, nifty500: seed },
    { date: '2025-12-15', simons: 498500, baselineSimons: 482000, lynch: 495000, baselineLynch: 501500, marks: 478000, baselineMarks: 472000, jhunjhunwala: 472000, baselineRj: 458000, stockmindsCore: 475000, baselineVarsity: 504000, nifty500: 501200 },
    { date: '2026-03-31', simons: 497100, baselineSimons: 466750, lynch: 490600, baselineLynch: 502000, marks: 452000, baselineMarks: 448850, jhunjhunwala: 455450, baselineRj: 437450, stockmindsCore: 450650, baselineVarsity: 506250, nifty500: 501800 },
  ];
}
