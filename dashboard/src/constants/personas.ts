import { getAgentName } from '../lib/agentNames';

/**
 * Centralized Single Source of Truth (SSOT) for Persona philosophy/school/horizon metadata.
 *
 * Display names (displayName/shortName/llmDisplayName/rulesDisplayName and the
 * getAgentDisplayName()/getBasePersonaName() resolvers below) all delegate to the one shared
 * name map in src/lib/agentNames.ts -- Aritro's short names (Jimmy, Pete, Howie, RJ, Varsity,
 * and their "... Core" rules twins). This file itself only owns the philosophy/school/horizon
 * copy, which is unrelated to which name is shown.
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
    displayName: getAgentName('simons'),
    shortName: getAgentName('simons'),
    isRules: false,
    philosophy: 'Quantitative Momentum',
    school: 'Statistical Momentum & Volatility Parity',
    horizon: '1–10 Days',
  },
  'baseline-simons-rules': {
    id: 'baseline-simons-rules',
    baseKey: 'simons',
    displayName: getAgentName('baseline-simons-rules'),
    shortName: getAgentName('baseline-simons-rules'),
    isRules: true,
    philosophy: 'Quantitative Momentum',
    school: 'Statistical Momentum & Volatility Parity',
    horizon: '1–10 Days',
  },

  // Varsity track
  varsity: {
    id: 'varsity',
    baseKey: 'varsity',
    displayName: getAgentName('varsity'),
    shortName: getAgentName('varsity'),
    isRules: false,
    philosophy: 'Dual-Confluence Swing',
    school: 'Dual Confluence · Solvency DCF + EMA Momentum',
    horizon: '5–20 Days',
  },
  'stockminds-core': {
    id: 'stockminds-core',
    baseKey: 'varsity',
    displayName: getAgentName('stockminds-core'),
    shortName: getAgentName('stockminds-core'),
    isRules: false,
    philosophy: 'Dual-Confluence Swing',
    school: 'Dual Confluence · Solvency DCF + EMA Momentum',
    horizon: '5–20 Days',
  },
  'baseline-varsity-rules': {
    id: 'baseline-varsity-rules',
    baseKey: 'varsity',
    displayName: getAgentName('baseline-varsity-rules'),
    shortName: getAgentName('baseline-varsity-rules'),
    isRules: true,
    philosophy: 'Dual-Confluence Swing',
    school: 'Dual Confluence · Solvency DCF + EMA Momentum',
    horizon: '5–20 Days',
  },

  // Lynch track
  lynch: {
    id: 'lynch',
    baseKey: 'lynch',
    displayName: getAgentName('lynch'),
    shortName: getAgentName('lynch'),
    isRules: false,
    philosophy: 'GARP Compounding',
    school: 'GARP Framework · PEG Ratio <= 1.0 · Durable ROCE',
    horizon: '15–60 Days',
  },
  'baseline-lynch-rules': {
    id: 'baseline-lynch-rules',
    baseKey: 'lynch',
    displayName: getAgentName('baseline-lynch-rules'),
    shortName: getAgentName('baseline-lynch-rules'),
    isRules: true,
    philosophy: 'GARP Compounding',
    school: 'GARP Framework · PEG Ratio <= 1.0 · Durable ROCE',
    horizon: '15–60 Days',
  },

  // Marks track
  marks: {
    id: 'marks',
    baseKey: 'marks',
    displayName: getAgentName('marks'),
    shortName: getAgentName('marks'),
    isRules: false,
    philosophy: 'Contrarian Value',
    school: 'Second-Level Thinking · Cyclical Distress · Margin of Safety',
    horizon: '30–90 Days',
  },
  'baseline-marks-rules': {
    id: 'baseline-marks-rules',
    baseKey: 'marks',
    displayName: getAgentName('baseline-marks-rules'),
    shortName: getAgentName('baseline-marks-rules'),
    isRules: true,
    philosophy: 'Contrarian Value',
    school: 'Second-Level Thinking · Cyclical Distress · Margin of Safety',
    horizon: '30–90 Days',
  },

  // Jhunjhunwala track
  jhunjhunwala: {
    id: 'jhunjhunwala',
    baseKey: 'jhunjhunwala',
    displayName: getAgentName('jhunjhunwala'),
    shortName: getAgentName('jhunjhunwala'),
    isRules: false,
    philosophy: 'Secular Domestic Growth',
    school: 'Structural Compounding · Promoter Skin-in-the-Game',
    horizon: '90–180 Days',
  },
  'baseline-rj-rules': {
    id: 'baseline-rj-rules',
    baseKey: 'jhunjhunwala',
    displayName: getAgentName('baseline-rj-rules'),
    shortName: getAgentName('baseline-rj-rules'),
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
    shortLabel: getAgentName('simons'),
    llmId: 'simons',
    rulesId: 'baseline-simons-rules',
    llmDisplayName: getAgentName('simons'),
    rulesDisplayName: getAgentName('baseline-simons-rules'),
    philosophy: 'Quantitative Momentum',
    school: 'Statistical Momentum & Volatility Parity',
    horizon: '1–10 Days',
  },
  {
    id: 'varsity',
    personaKey: 'varsity',
    name: 'Dual-Confluence Swing',
    shortLabel: getAgentName('varsity'),
    llmId: 'varsity',
    rulesId: 'baseline-varsity-rules',
    llmDisplayName: getAgentName('varsity'),
    rulesDisplayName: getAgentName('baseline-varsity-rules'),
    philosophy: 'Dual-Confluence Swing',
    school: 'Dual Confluence · Solvency DCF + EMA Momentum',
    horizon: '5–20 Days',
  },
  {
    id: 'lynch',
    personaKey: 'lynch',
    name: 'GARP Compounding',
    shortLabel: getAgentName('lynch'),
    llmId: 'lynch',
    rulesId: 'baseline-lynch-rules',
    llmDisplayName: getAgentName('lynch'),
    rulesDisplayName: getAgentName('baseline-lynch-rules'),
    philosophy: 'GARP Compounding',
    school: 'GARP Framework · PEG Ratio <= 1.0 · Durable ROCE',
    horizon: '15–60 Days',
  },
  {
    id: 'marks',
    personaKey: 'marks',
    name: 'Contrarian Value',
    shortLabel: getAgentName('marks'),
    llmId: 'marks',
    rulesId: 'baseline-marks-rules',
    llmDisplayName: getAgentName('marks'),
    rulesDisplayName: getAgentName('baseline-marks-rules'),
    philosophy: 'Contrarian Value',
    school: 'Second-Level Thinking · Cyclical Distress · Margin of Safety',
    horizon: '30–90 Days',
  },
  {
    id: 'jhunjhunwala',
    personaKey: 'jhunjhunwala',
    name: 'Secular Domestic Growth',
    shortLabel: getAgentName('jhunjhunwala'),
    llmId: 'jhunjhunwala',
    rulesId: 'baseline-rj-rules',
    llmDisplayName: getAgentName('jhunjhunwala'),
    rulesDisplayName: getAgentName('baseline-rj-rules'),
    philosophy: 'Secular Domestic Growth',
    school: 'Structural Compounding · Promoter Skin-in-the-Game',
    horizon: '90–180 Days',
  },
];

/**
 * Resolver for any agentId (or, failing that, a raw name string) -- delegates to the shared
 * agentNames.ts map. This is a fallback label for the handful of places with no live
 * leaderboard fetch in scope; wherever a page already has a fetched agent/leaderboard entry,
 * prefer calling getAgentName(id, entry.name) directly over this.
 */
export function getAgentDisplayName(agentIdOrName: string): string {
  if (!agentIdOrName) return 'Agent';
  const clean = agentIdOrName.trim();
  const lower = clean.toLowerCase();

  if (CANONICAL_PERSONAS[clean]) return CANONICAL_PERSONAS[clean].displayName;
  if (CANONICAL_PERSONAS[lower]) return CANONICAL_PERSONAS[lower].displayName;

  // Not a known id -- try it as a raw id anyway, then fall back to cleaning up the string.
  const direct = getAgentName(lower, '');
  if (direct) return direct;

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
 * Returns the base persona's short name without the " Core" rules-twin suffix
 * (e.g. "Jimmy", "Pete", "Howie", "RJ", "Varsity").
 */
export function getBasePersonaName(agentIdOrName: string): string {
  const full = getAgentDisplayName(agentIdOrName);
  return full.replace(/\s+Core$/i, '');
}
