/**
 * The one shared map of short, friendly agent display names -- the names Aritro gave each
 * agent (originally in constants/personas.ts, theme/tokens.ts's STRATEGY_THEME, and
 * services/mockData.ts; see `git show 0072cc9:dashboard/src/constants/personas.ts` for the
 * commit that introduced them). Keyed by the real backend agent id (`GET /api/leaderboard`'s
 * `id` field), so it applies cleanly to real data -- the backend's own `name` field is only
 * ever used as the fallback for an id this map doesn't recognize.
 *
 * This is the ONLY place these short names are defined. Every page/component that shows an
 * agent label (standings, tables, chart legends, tooltips, filters, tab headings) should call
 * getAgentName(id, backendName) rather than hard-coding a name or inventing its own mapping.
 *
 * Deliberately NOT used for: the Home page's editorial "Five Observed Personas" cards and
 * "Schools of Thought" copy, where the full real name (e.g. "Peter Lynch") is the point --
 * those are philosophy/biography titles, not agent-data labels.
 */
export const AGENT_SHORT_NAMES: Record<string, string> = {
  simons: 'Jimmy',
  'baseline-simons-rules': 'Jimmy Core',
  varsity: 'Varsity',
  'stockminds-core': 'Varsity', // legacy alias for the same agent, kept for safety
  'baseline-varsity-rules': 'Varsity Core',
  lynch: 'Pete',
  'baseline-lynch-rules': 'Pete Core',
  marks: 'Howie',
  'baseline-marks-rules': 'Howie Core',
  jhunjhunwala: 'RJ',
  'baseline-rj-rules': 'RJ Core',
};

/**
 * Resolves the short display name for a real backend agent id. Falls back to the backend's
 * own name (or the raw id, or "Agent") for any id this map doesn't cover -- never invents a
 * short name for an agent Aritro didn't name.
 */
export function getAgentName(id: string | null | undefined, fallbackName?: string | null): string {
  if (id && AGENT_SHORT_NAMES[id]) return AGENT_SHORT_NAMES[id];
  return fallbackName || id || 'Agent';
}

/**
 * Descriptive "<Surname> Rules" label for a Rules twin -- used ONLY by the Agent Terminal's
 * Twin card (an explainer: "RULES TWIN · Simons Rules · Same stocks, no AI"), which needs a
 * name that reads as a sentence rather than the compact "<ShortName> Core" label used
 * everywhere else data is tabular (Leaderboard, Backtest, Telemetry, chart legends). Keyed
 * by the LLM agent's own id (never the baseline-*-rules id), so callers normalize to the
 * base persona key first. AGENT_SHORT_NAMES (and every other consumer) is unaffected -- this
 * is additive, not a rename of the shared short-name map.
 */
export const AGENT_RULES_TWIN_LABEL: Record<string, string> = {
  simons: 'Simons Rules',
  lynch: 'Lynch Rules',
  marks: 'Marks Rules',
  jhunjhunwala: 'Jhunjhunwala Rules',
  varsity: 'Varsity Rules',
};

export function getRulesTwinLabel(baseLlmId: string | null | undefined): string | null {
  if (!baseLlmId) return null;
  return AGENT_RULES_TWIN_LABEL[baseLlmId] || null;
}
