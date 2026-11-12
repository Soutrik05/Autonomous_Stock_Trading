// TypeScript definitions matching the StockMinds backend REST API (Plan_v3 Part IV)

export type AgentId = 
  | 'simons' 
  | 'lynch' 
  | 'marks' 
  | 'jhunjhunwala' 
  | 'stockminds-core' 
  | 'baseline-simons-rules'
  | 'baseline-lynch-rules'
  | 'baseline-marks-rules'
  | 'baseline-rj-rules'
  | 'baseline-varsity-rules'
  | (string & {});

export interface AgentLeaderboardEntry {
  id: AgentId;
  name: string;
  philosophy: string;
  horizonDays: string;
  navPaise: number;
  startingCapitalPaise: number;
  returnPct: number;
  alphaVsBenchmarkPct: number;
  sharpeRatio: number;
  maxDrawdownPct: number;
  winRatePct: number;
  faithfulnessRatePct: number;
  totalTrades: number;
  closedTrades: number;
  isProvisional: boolean; // true when closedTrades < 30
  activePositionsCount: number;
  lastActiveDate: string;
  foundationModel?: string | null;
  evidenceLabel?: string;
  sampleNotice?: string;
}

export type PositionStatus = 'OPEN' | 'CLOSED';

export type ForensicTag = 
  | 'WIN_MULTI_CONFLUENCE'
  | 'WIN_TREND_CONTINUATION'
  | 'WIN_CATALYST'
  | 'LOSS_STOP_HIT'
  | 'LOSS_REGIME_CHANGE'
  | 'LOSS_DISCIPLINE_BREACH'
  | 'LOSS_VOLATILITY_EXPANSION'
  | 'HOLD_PROLONGED'
  | 'NONE';

export interface Position {
  id: number;
  agentId: AgentId;
  symbol: string;
  companyName: string;
  sector: string;
  quantity: number;
  entryPricePaise: number;
  currentPricePaise: number;
  exitPricePaise?: number;
  stopLossPaise: number;
  targetPricePaise?: number;
  status: PositionStatus;
  unrealizedPnlPaise: number;
  unrealizedPnlPct: number;
  realizedPnlPaise?: number;
  realizedPnlPct?: number;
  openedAt: string;
  closedAt?: string;
  holdDays: number;
  forensicTag: ForensicTag;
  isFrozen: boolean;
  thesisSummary: string;
}

export type OrderSide = 'BUY' | 'SELL';
export type OrderType = 'LIMIT' | 'STOP_LOSS' | 'MARKET';
export type OrderStatus = 'PENDING' | 'FILLED' | 'CANCELLED' | 'EXPIRED' | 'REJECTED';

export interface Order {
  id: number;
  agentId: AgentId;
  symbol: string;
  side: OrderSide;
  orderType: OrderType;
  quantity: number;
  limitPricePaise: number;
  entryLowPaise?: number;
  entryHighPaise?: number;
  filledPricePaise?: number;
  status: OrderStatus;
  rejectionReason?: string;
  submittedAt: string;
  filledAt?: string;
  statutoryChargesPaise: number;
  slippagePaise: number;
}

export interface CitedMetric {
  name: string;
  citedValue: number | string;
  actualSnapshotValue: number | string;
  tolerance: string;
  isFaithful: boolean;
}

export interface Decision {
  id: number;
  agentId: AgentId;
  symbol: string;
  decisionDate: string;
  action: 'BUY' | 'HOLD' | 'SELL';
  rationale: string;
  preMortemRisk?: string;
  citedMetrics: CitedMetric[];
  faithfulnessScore: number; // 0.0 to 1.0 (or %)
  sizingFidelityScore: number;
  candidateRank: number;
  stageReached: string;
  allocatedPaise?: number;
}

export interface HeuristicMemory {
  id: number;
  agentId: AgentId;
  kind: 'SEEK' | 'AVOID';
  ruleDescription: string;
  triggerPredicate: string;
  status: 'DISCOVERED' | 'TESTING' | 'ACTIVE' | 'REINFORCED' | 'DEPRECATED';
  confidenceScore: number;
  timesApplied: number;
  successRatePct: number;
  createdAt: string;
  lastTestedAt: string;
}

export interface NavHistoryPoint {
  date: string;
  simons: number;
  baselineSimons?: number;
  lynch: number;
  baselineLynch?: number;
  marks: number;
  baselineMarks?: number;
  jhunjhunwala: number;
  baselineRj?: number;
  stockmindsCore: number;
  baselineVarsity?: number;
  nifty500: number;
}

export interface AgentComparisonStats {
  id?: string;
  name?: string;
  navPaise: number;
  returnPct: number;
  sharpe: number;
  maxDrawdownPct: number;
  winRatePct: number;
  faithfulnessRatePct?: number;
  trades: number;
}

export interface HorizonReturnComparison {
  horizonDays: number;
  llmBuyAvgPct: number;
  llmHoldAvgPct: number;
  rulesBuyAvgPct: number;
  nifty500AvgPct: number;
  selectionAlphaPct: number;
  // Backward compatibility aliases
  llmSimonsBuyAvgPct?: number;
  llmSimonsHoldAvgPct?: number;
  rulesSimonsBuyAvgPct?: number;
}

export interface BaselineComparison {
  personaId?: string;
  llmAgent?: AgentComparisonStats;
  rulesAgent?: AgentComparisonStats;
  llmSimons: AgentComparisonStats;
  rulesSimons: AgentComparisonStats;
  nifty500: {
    benchmarkNavPaise: number;
    returnPct: number;
    maxDrawdownPct: number;
  };
  candidateSelectionAlpha: number;
  horizonReturns: HorizonReturnComparison[];
}

export type EventSeverity = 'INFO' | 'SUCCESS' | 'WARNING' | 'ERROR';

export interface ActivityEvent {
  id: string;
  timestamp: string;
  eventType: 
    | 'ORDER_SUBMITTED' 
    | 'ORDER_FILLED' 
    | 'ORDER_EXPIRED' 
    | 'STOP_TRIGGERED' 
    | 'CAP_BREACH' 
    | 'HEURISTIC_DISCOVERED' 
    | 'DAILY_SETTLEMENT' 
    | 'PIPELINE_COMPLETE';
  agentId?: AgentId;
  symbol?: string;
  message: string;
  severity: EventSeverity;
  details?: Record<string, string | number>;
}

export interface PipelineHealthJob {
  jobName: string;
  cadence: string;
  status: 'SUCCESS' | 'RUNNING' | 'FAILED' | 'PENDING' | 'INTERRUPTED' | 'SKIPPED_HOLIDAY' | string;
  lastRunAt: string;
  durationSec: number;
  recordsProcessed?: number;
  errorMessage?: string;
}

export interface BacktestRegimeWindow {
  windowId: string;
  name: string;
  startDate: string;
  endDate: string;
  marketRegime: 'BULL' | 'CORRECTION' | 'SIDEWAYS';
  nifty500ReturnPct: number;
  agents: AgentLeaderboardEntry[];
  resolvedDurations: {
    agentId: AgentId;
    agentName: string;
    intendedHorizonDays: string;
    empiricalAvgHoldDays: number;
    maxHoldDays: number;
    resolvedCyclesCount: number;
  }[];
}


export interface AgentWatchlistItem {
  agentId: string;
  ticker: string;
  companyName: string;
  sector: string;
  addedOn: string;
  ttlDays: number;
  expiresOn: string;
  intensityScore: number;
}

export interface FunnelStageCount {
  key: string;
  count: number;
}

export interface FunnelEntry {
  agentId: string;
  runDate: string;
  stages: FunnelStageCount[];
}


export interface MarketContext {
  tradeDate: string | null;
  regime: string;
  indiaVix: number;
  fiiNetCr: number | null;
  diiNetCr: number | null;
  nifty50Trend: string;
  nifty500Trend: string;
  advanceDecline: number | null;
}
