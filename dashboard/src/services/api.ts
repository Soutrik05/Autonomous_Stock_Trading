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
      lynch: vals.lynch ?? 10000000,
      marks: vals.marks ?? 10000000,
      jhunjhunwala: vals.jhunjhunwala ?? 10000000,
      stockmindsCore: vals.varsity ?? vals['stockminds-core'] ?? 10000000,
      baselineSimons: vals['baseline-simons-rules'] ?? 10000000,
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

  async checkBackendConnection(): Promise<boolean> {
    try {
      const res = await fetch(`${BASE_URL}/health`, { method: 'GET', signal: AbortSignal.timeout(2000) });
      return res.ok;
    } catch {
      return false;
    }
  },
};
