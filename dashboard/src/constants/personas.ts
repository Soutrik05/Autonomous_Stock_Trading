/**
 * Centralized Single Source of Truth (SSOT) for Persona & Strategy Names.
 *
 * Display names here MUST mirror what the real backend returns from `GET /api/leaderboard`
 * (`name` field) for the live agents. This file exists only so pages that have no live
 * leaderboard fetch in scope (chart legends, the Telemetry agent filter, event rows that
 * carry only an `agent_id`) can still render a human name -- it is a fallback label, never
 * a value that overrides or invents data from a real fetch.
 */

export interface PersonaMeta {
  id: string;
  baseKey: 'simons' | 'varsity' | 'lynch' | 'marks' | 'jhunjhunwala';
  displayName: string;
  shortName: string;
  isRules: boolean;
  philosophy: string;
  school: string;
  horizon: string;
}

export interface PhilosophyPair {
  id: 'simons' | 'varsity' | 'lynch' | 'marks' | 'jhunjhunwala';
  personaKey: string;
  name: string;
  shortLabel: string;
  llmId: string;
  rulesId: string;
  llmDisplayName: string;
  rulesDisplayName: string;
  philosophy: string;
  school: string;
  horizon: string;
}

export const CANONICAL_PERSONAS: Record<string, PersonaMeta> = {
  // Simons track
  simons: {
    id: 'simons',
    baseKey: 'simons',
    displayName: 'Jim Simons',
    shortName: 'Jim Simons',
    isRules: false,
    philosophy: 'Quantitative Momentum',
    school: 'Statistical Momentum & Volatility Parity',
    horizon: '1–10 Days',
  },
  'baseline-simons-rules': {
    id: 'baseline-simons-rules',
    baseKey: 'simons',
    displayName: 'Baseline Simons Rules',
    shortName: 'Simons Rules',
    isRules: true,
    philosophy: 'Quantitative Momentum',
    school: 'Statistical Momentum & Volatility Parity',
    horizon: '1–10 Days',
  },

  // Varsity track
  varsity: {
    id: 'varsity',
    baseKey: 'varsity',
    displayName: 'StockMinds Core',
    shortName: 'StockMinds Core',
    isRules: false,
    philosophy: 'Dual-Confluence Swing',
    school: 'Dual Confluence · Solvency DCF + EMA Momentum',
    horizon: '5–20 Days',
  },
  'stockminds-core': {
    id: 'stockminds-core',
    baseKey: 'varsity',
    displayName: 'StockMinds Core',
    shortName: 'StockMinds Core',
    isRules: false,
    philosophy: 'Dual-Confluence Swing',
    school: 'Dual Confluence · Solvency DCF + EMA Momentum',
    horizon: '5–20 Days',
  },
  'baseline-varsity-rules': {
    id: 'baseline-varsity-rules',
    baseKey: 'varsity',
    displayName: 'Baseline Varsity Rules',
    shortName: 'Varsity Rules',
    isRules: true,
    philosophy: 'Dual-Confluence Swing',
    school: 'Dual Confluence · Solvency DCF + EMA Momentum',
    horizon: '5–20 Days',
  },

  // Lynch track
  lynch: {
    id: 'lynch',
    baseKey: 'lynch',
    displayName: 'Peter Lynch',
    shortName: 'Peter Lynch',
    isRules: false,
    philosophy: 'GARP Compounding',
    school: 'GARP Framework · PEG Ratio <= 1.0 · Durable ROCE',
    horizon: '15–60 Days',
  },
  'baseline-lynch-rules': {
    id: 'baseline-lynch-rules',
    baseKey: 'lynch',
    displayName: 'Baseline Lynch Rules',
    shortName: 'Lynch Rules',
    isRules: true,
    philosophy: 'GARP Compounding',
    school: 'GARP Framework · PEG Ratio <= 1.0 · Durable ROCE',
    horizon: '15–60 Days',
  },

  // Marks track
  marks: {
    id: 'marks',
    baseKey: 'marks',
    displayName: 'Howard Marks',
    shortName: 'Howard Marks',
    isRules: false,
    philosophy: 'Contrarian Value',
    school: 'Second-Level Thinking · Cyclical Distress · Margin of Safety',
    horizon: '30–90 Days',
  },
  'baseline-marks-rules': {
    id: 'baseline-marks-rules',
    baseKey: 'marks',
    displayName: 'Baseline Marks Rules',
    shortName: 'Marks Rules',
    isRules: true,
    philosophy: 'Contrarian Value',
    school: 'Second-Level Thinking · Cyclical Distress · Margin of Safety',
    horizon: '30–90 Days',
  },

  // Jhunjhunwala track
  jhunjhunwala: {
    id: 'jhunjhunwala',
    baseKey: 'jhunjhunwala',
    displayName: 'Rakesh Jhunjhunwala',
    shortName: 'Rakesh Jhunjhunwala',
    isRules: false,
    philosophy: 'Secular Domestic Growth',
    school: 'Structural Compounding · Promoter Skin-in-the-Game',
    horizon: '90–180 Days',
  },
  'baseline-rj-rules': {
    id: 'baseline-rj-rules',
    baseKey: 'jhunjhunwala',
    displayName: 'Baseline Jhunjhunwala Rules',
    shortName: 'Jhunjhunwala Rules',
    isRules: true,
    philosophy: 'Secular Domestic Growth',
    school: 'Structural Compounding · Promoter Skin-in-the-Game',
    horizon: '90–180 Days',
  },
};

/**
 * Ordered philosophy pairs for comparison, backtest matrices, and cross-regime synthesis.
 */
export const PHILOSOPHY_PAIRS: PhilosophyPair[] = [
  {
    id: 'simons',
    personaKey: 'simons',
    name: 'Quantitative Momentum',
    shortLabel: 'Jim Simons',
    llmId: 'simons',
    rulesId: 'baseline-simons-rules',
    llmDisplayName: 'Jim Simons',
    rulesDisplayName: 'Baseline Simons Rules',
    philosophy: 'Quantitative Momentum',
    school: 'Statistical Momentum & Volatility Parity',
    horizon: '1–10 Days',
  },
  {
    id: 'varsity',
    personaKey: 'varsity',
    name: 'Dual-Confluence Swing',
    shortLabel: 'StockMinds Core',
    llmId: 'varsity',
    rulesId: 'baseline-varsity-rules',
    llmDisplayName: 'StockMinds Core',
    rulesDisplayName: 'Baseline Varsity Rules',
    philosophy: 'Dual-Confluence Swing',
    school: 'Dual Confluence · Solvency DCF + EMA Momentum',
    horizon: '5–20 Days',
  },
  {
    id: 'lynch',
    personaKey: 'lynch',
    name: 'GARP Compounding',
    shortLabel: 'Peter Lynch',
    llmId: 'lynch',
    rulesId: 'baseline-lynch-rules',
    llmDisplayName: 'Peter Lynch',
    rulesDisplayName: 'Baseline Lynch Rules',
    philosophy: 'GARP Compounding',
    school: 'GARP Framework · PEG Ratio <= 1.0 · Durable ROCE',
    horizon: '15–60 Days',
  },
  {
    id: 'marks',
    personaKey: 'marks',
    name: 'Contrarian Value',
    shortLabel: 'Howard Marks',
    llmId: 'marks',
    rulesId: 'baseline-marks-rules',
    llmDisplayName: 'Howard Marks',
    rulesDisplayName: 'Baseline Marks Rules',
    philosophy: 'Contrarian Value',
    school: 'Second-Level Thinking · Cyclical Distress · Margin of Safety',
    horizon: '30–90 Days',
  },
  {
    id: 'jhunjhunwala',
    personaKey: 'jhunjhunwala',
    name: 'Secular Domestic Growth',
    shortLabel: 'Rakesh Jhunjhunwala',
    llmId: 'jhunjhunwala',
    rulesId: 'baseline-rj-rules',
    llmDisplayName: 'Rakesh Jhunjhunwala',
    rulesDisplayName: 'Baseline Jhunjhunwala Rules',
    philosophy: 'Secular Domestic Growth',
    school: 'Structural Compounding · Promoter Skin-in-the-Game',
    horizon: '90–180 Days',
  },
];

/**
 * Resolver function to retrieve the real backend display name for any agentId or raw name
 * string. This is a fallback label for the handful of places with no live leaderboard fetch
 * in scope -- wherever a page already has a fetched agent/leaderboard entry, prefer its own
 * `.name` field over this resolver.
 */
export function getAgentDisplayName(agentIdOrName: string): string {
  if (!agentIdOrName) return 'Agent';
  const clean = agentIdOrName.trim();
  const lower = clean.toLowerCase();

  // Direct ID hit
  if (CANONICAL_PERSONAS[clean]) {
    return CANONICAL_PERSONAS[clean].displayName;
  }
  if (CANONICAL_PERSONAS[lower]) {
    return CANONICAL_PERSONAS[lower].displayName;
  }

  const isRules =
    lower.startsWith('baseline-') ||
    lower.includes('rules') ||
    lower.includes('control');

  // Substring match by persona key
  if (lower.includes('simons')) {
    return isRules ? 'Baseline Simons Rules' : 'Jim Simons';
  }
  if (lower.includes('varsity') || lower.includes('stockminds')) {
    return isRules ? 'Baseline Varsity Rules' : 'StockMinds Core';
  }
  if (lower.includes('lynch')) {
    return isRules ? 'Baseline Lynch Rules' : 'Peter Lynch';
  }
  if (lower.includes('marks')) {
    return isRules ? 'Baseline Marks Rules' : 'Howard Marks';
  }
  if (lower.includes('jhunjhunwala') || lower.includes('rj')) {
    return isRules ? 'Baseline Jhunjhunwala Rules' : 'Rakesh Jhunjhunwala';
  }

  // Fallback cleanup
  return clean
    .replace(/\s*\([^)]*\)/gi, '')
    .replace(/\s*rules\s*/gi, '')
    .replace(/^baseline[-:\s]*/i, '')
    .trim();
}

/**
 * Returns true if the strategy is a deterministic rules-based baseline.
 */
export function isRulesStrategy(agentIdOrName: string): boolean {
  if (!agentIdOrName) return false;
  const lower = agentIdOrName.toLowerCase();
  return (
    lower.startsWith('baseline-') ||
    lower.includes('rules') ||
    lower.includes('control')
  );
}

/**
 * Returns the base persona name without the "Baseline ... Rules" wrapper
 * (e.g. "Jim Simons", "Peter Lynch", "Howard Marks", "Rakesh Jhunjhunwala", "StockMinds Core").
 */
export function getBasePersonaName(agentIdOrName: string): string {
  const full = getAgentDisplayName(agentIdOrName);
  return full.replace(/^Baseline\s+/i, '').replace(/\s+Rules$/i, '');
}
