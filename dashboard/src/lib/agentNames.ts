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
/** The 5 LLM agents and their 5 Rules twins, in the one shared order used throughout the
 * Agent Terminal and the Comparison page (Simons, Lynch, Marks, Jhunjhunwala, Varsity). Real
 * backend agent ids (confirmed against GET /api/leaderboard). */
export const LLM_IDS = ['simons', 'lynch', 'marks', 'jhunjhunwala', 'varsity'];
export const RULES_IDS = ['baseline-simons-rules', 'baseline-lynch-rules', 'baseline-marks-rules', 'baseline-rj-rules', 'baseline-varsity-rules'];

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
 * Descriptive "<Surname> Rules" label for a Rules twin -- the ONE name every Rules agent
 * should show wherever the page is explaining the LLM/Rules pairing rather than just listing
 * data compactly: the Agent Terminal's header/Twin card, the Switch-agent dropdown (both
 * places it's used), and the Comparison page. Keyed directly by the baseline-*-rules id.
 * Deliberately NOT used by the dense data tables (Leaderboard, Backtest, Telemetry, chart
 * legends), which keep the "<ShortName> Core" label from AGENT_SHORT_NAMES above -- that is
 * a separate, intentional convention for tabular density, not a bug.
 */
export const AGENT_RULES_LABEL: Record<string, string> = {
  'baseline-simons-rules': 'Simons Rules',
  'baseline-lynch-rules': 'Lynch Rules',
  'baseline-marks-rules': 'Marks Rules',
  'baseline-rj-rules': 'RJ Rules',
  'baseline-varsity-rules': 'Varsity Rules',
};

/**
 * The one shared helper for every "explainer" context (Agent Terminal header + Twin card,
 * Switch-agent dropdown, Comparison page): a Rules agent gets its descriptive "<Surname>
 * Rules" label, an LLM agent gets its normal short name from AGENT_SHORT_NAMES. Every one of
 * those call sites should use THIS function, not getAgentName() directly, so there is exactly
 * one code path deciding what a Rules agent is called outside the dense data tables.
 */
export function getAgentLabel(id: string | null | undefined, fallbackName?: string | null): string {
  if (!id) return fallbackName || 'Agent';
  const normalized = id === 'stockminds-core' ? 'varsity' : id;
  if (AGENT_RULES_LABEL[normalized]) return AGENT_RULES_LABEL[normalized];
  return getAgentName(normalized, fallbackName);
}
