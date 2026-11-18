/**
 * Centralized Single Source of Truth (SSOT) for Persona & Strategy Names
 * 
 * Canonical Personas:
 * - Jimmy   (Quant Momentum, inspired by Jim Simons)        / Jimmy Core   (Rules Control)
 * - Pete    (GARP Compounding, inspired by Peter Lynch)      / Pete Core    (Rules Control)
 * - Howie   (Contrarian Value, inspired by Howard Marks)     / Howie Core   (Rules Control)
 * - RJ      (Secular Growth, inspired by Rakesh Jhunjhunwala)/ RJ Core      (Rules Control)
 * - Varsity (Dual-Confluence, inspired by Zerodha Varsity)   / Varsity Core (Rules Control)
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
    displayName: 'Jimmy',
    shortName: 'Jimmy',
    isRules: false,
    philosophy: 'Quantitative Momentum',
    school: 'Statistical Momentum & Volatility Parity',
    horizon: '1–10 Days',
  },
  'baseline-simons-rules': {
    id: 'baseline-simons-rules',
    baseKey: 'simons',
    displayName: 'Jimmy Core',
    shortName: 'Jimmy Core',
    isRules: true,
    philosophy: 'Quantitative Momentum',
    school: 'Statistical Momentum & Volatility Parity',
    horizon: '1–10 Days',
  },

  // Varsity track
  varsity: {
    id: 'varsity',
    baseKey: 'varsity',
    displayName: 'Varsity',
    shortName: 'Varsity',
    isRules: false,
    philosophy: 'Dual-Confluence Swing',
    school: 'Dual Confluence · Solvency DCF + EMA Momentum',
    horizon: '5–20 Days',
  },
  'stockminds-core': {
    id: 'stockminds-core',
    baseKey: 'varsity',
    displayName: 'Varsity',
    shortName: 'Varsity',
    isRules: false,
    philosophy: 'Dual-Confluence Swing',
    school: 'Dual Confluence · Solvency DCF + EMA Momentum',
    horizon: '5–20 Days',
  },
  'baseline-varsity-rules': {
    id: 'baseline-varsity-rules',
    baseKey: 'varsity',
    displayName: 'Varsity Core',
    shortName: 'Varsity Core',
    isRules: true,
    philosophy: 'Dual-Confluence Swing',
    school: 'Dual Confluence · Solvency DCF + EMA Momentum',
    horizon: '5–20 Days',
  },

  // Lynch track
  lynch: {
    id: 'lynch',
    baseKey: 'lynch',
    displayName: 'Pete',
    shortName: 'Pete',
    isRules: false,
    philosophy: 'GARP Compounding',
    school: 'GARP Framework · PEG Ratio <= 1.0 · Durable ROCE',
    horizon: '15–60 Days',
  },
  'baseline-lynch-rules': {
    id: 'baseline-lynch-rules',
    baseKey: 'lynch',
    displayName: 'Pete Core',
    shortName: 'Pete Core',
    isRules: true,
    philosophy: 'GARP Compounding',
    school: 'GARP Framework · PEG Ratio <= 1.0 · Durable ROCE',
    horizon: '15–60 Days',
  },

  // Marks track
  marks: {
    id: 'marks',
    baseKey: 'marks',
    displayName: 'Howie',
    shortName: 'Howie',
    isRules: false,
    philosophy: 'Contrarian Value',
    school: 'Second-Level Thinking · Cyclical Distress · Margin of Safety',
    horizon: '30–90 Days',
  },
  'baseline-marks-rules': {
    id: 'baseline-marks-rules',
    baseKey: 'marks',
    displayName: 'Howie Core',
    shortName: 'Howie Core',
    isRules: true,
    philosophy: 'Contrarian Value',
    school: 'Second-Level Thinking · Cyclical Distress · Margin of Safety',
    horizon: '30–90 Days',
  },

  // Jhunjhunwala track
  jhunjhunwala: {
    id: 'jhunjhunwala',
    baseKey: 'jhunjhunwala',
    displayName: 'RJ',
    shortName: 'RJ',
    isRules: false,
    philosophy: 'Secular Domestic Growth',
    school: 'Structural Compounding · Promoter Skin-in-the-Game',
    horizon: '90–180 Days',
  },
  'baseline-rj-rules': {
    id: 'baseline-rj-rules',
    baseKey: 'jhunjhunwala',
    displayName: 'RJ Core',
    shortName: 'RJ Core',
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
    shortLabel: 'Jimmy',
    llmId: 'simons',
    rulesId: 'baseline-simons-rules',
    llmDisplayName: 'Jimmy',
    rulesDisplayName: 'Jimmy Core',
    philosophy: 'Quantitative Momentum',
    school: 'Statistical Momentum & Volatility Parity',
    horizon: '1–10 Days',
  },
  {
    id: 'varsity',
    personaKey: 'varsity',
    name: 'Dual-Confluence Swing',
    shortLabel: 'Varsity',
    llmId: 'varsity',
    rulesId: 'baseline-varsity-rules',
    llmDisplayName: 'Varsity',
    rulesDisplayName: 'Varsity Core',
    philosophy: 'Dual-Confluence Swing',
    school: 'Dual Confluence · Solvency DCF + EMA Momentum',
    horizon: '5–20 Days',
  },
  {
    id: 'lynch',
    personaKey: 'lynch',
    name: 'GARP Compounding',
    shortLabel: 'Pete',
    llmId: 'lynch',
    rulesId: 'baseline-lynch-rules',
    llmDisplayName: 'Pete',
    rulesDisplayName: 'Pete Core',
    philosophy: 'GARP Compounding',
    school: 'GARP Framework · PEG Ratio <= 1.0 · Durable ROCE',
    horizon: '15–60 Days',
  },
  {
    id: 'marks',
    personaKey: 'marks',
    name: 'Contrarian Value',
    shortLabel: 'Howie',
    llmId: 'marks',
    rulesId: 'baseline-marks-rules',
    llmDisplayName: 'Howie',
    rulesDisplayName: 'Howie Core',
    philosophy: 'Contrarian Value',
    school: 'Second-Level Thinking · Cyclical Distress · Margin of Safety',
    horizon: '30–90 Days',
  },
  {
    id: 'jhunjhunwala',
    personaKey: 'jhunjhunwala',
    name: 'Secular Domestic Growth',
    shortLabel: 'RJ',
    llmId: 'jhunjhunwala',
    rulesId: 'baseline-rj-rules',
    llmDisplayName: 'RJ',
    rulesDisplayName: 'RJ Core',
    philosophy: 'Secular Domestic Growth',
    school: 'Structural Compounding · Promoter Skin-in-the-Game',
    horizon: '90–180 Days',
  },
];

/**
 * Resolver function to retrieve canonical display name for any agentId or raw name string.
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
  if (lower.includes('simons') || lower.includes('jimmy')) {
    return isRules ? 'Jimmy Core' : 'Jimmy';
  }
  if (lower.includes('varsity') || lower.includes('stockminds')) {
    return isRules ? 'Varsity Core' : 'Varsity';
  }
  if (lower.includes('lynch') || lower.includes('pete')) {
    return isRules ? 'Pete Core' : 'Pete';
  }
  if (lower.includes('marks') || lower.includes('howie') || lower.includes('howard')) {
    return isRules ? 'Howie Core' : 'Howie';
  }
  if (lower.includes('jhunjhunwala') || lower.includes('rj') || lower.includes('rakesh')) {
    return isRules ? 'RJ Core' : 'RJ';
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
    lower.includes('control') ||
    lower.endsWith(' core')
  );
}

/**
 * Returns the base persona name without the Core suffix (e.g., Jimmy, Pete, Howie, RJ, Varsity).
 */
export function getBasePersonaName(agentIdOrName: string): string {
  const full = getAgentDisplayName(agentIdOrName);
  return full.replace(/\s+Core$/i, '');
}
