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
