/**
 * Plain-English persona copy for the Agent Terminal header (Portfolio.tsx) -- a short style
 * tag and a two-line description per agent id. These are NOT in the backend or in any other
 * file in the project; horizon and philosophy/school text already live in
 * constants/personas.ts (CANONICAL_PERSONAS) and are reused from there instead of being
 * duplicated here. The wording below was written from the persona rules already encoded in
 * Home.tsx's SCHOOLS_OF_THOUGHT copy and Portfolio.tsx's own (longer) persona profiles --
 * nothing here invents a rule the code doesn't have. Review this file's text directly; it is
 * the single place these short descriptions are defined.
 */

export interface PersonaCopy {
  /** Short tag shown next to the Horizon tag, e.g. "Short-term momentum". */
  styleTag: string;
  /** Plain-English, two-sentence-max description. Clamped to 2 lines in the UI. */
  description: string;
}

export const PERSONA_COPY: Record<string, PersonaCopy> = {
  simons: {
    styleTag: 'Short-term momentum',
    description:
      'Jimmy follows the Jim Simons style. He buys stocks that are already rising, checks that several signals agree, and sells fast when a stock turns against him.',
  },
  'baseline-simons-rules': {
    styleTag: 'Short-term momentum',
    description:
      'Jimmy Core runs the same momentum checks as Jimmy, but as fixed math with no AI -- it buys the same kind of breakouts and exits on the same signals, every time.',
  },
  varsity: {
    styleTag: 'Swing value + trend',
    description:
      'Varsity follows the Zerodha Varsity style. It only buys financially healthy companies that are also pulling back to a rising trend line, and skips the trade if either check fails.',
  },
  'stockminds-core': {
    styleTag: 'Swing value + trend',
    description:
      'Varsity follows the Zerodha Varsity style. It only buys financially healthy companies that are also pulling back to a rising trend line, and skips the trade if either check fails.',
  },
  'baseline-varsity-rules': {
    styleTag: 'Swing value + trend',
    description:
      'Varsity Core runs the same solvency-and-trend checks as Varsity, but as fixed math with no AI -- the same two conditions, applied the same way, every time.',
  },
  lynch: {
    styleTag: 'Growth at a fair price',
    description:
      'Pete follows the Peter Lynch style. He buys growing, profitable companies while their price still looks cheap next to that growth, and holds through short-term noise.',
  },
  'baseline-lynch-rules': {
    styleTag: 'Growth at a fair price',
    description:
      'Pete Core runs the same growth-and-value checks as Pete, but as fixed math with no AI -- the same valuation and quality thresholds, applied the same way, every time.',
  },
  marks: {
    styleTag: 'Contrarian value',
    description:
      "Howie follows the Howard Marks style. He looks for good businesses the market has given up on, buys them cheap, and sizes positions so a mistake doesn't hurt too much.",
  },
  'baseline-marks-rules': {
    styleTag: 'Contrarian value',
    description:
      'Howie Core runs the same distress-and-safety checks as Howie, but as fixed math with no AI -- the same entry and sizing rules, applied the same way, every time.',
  },
  jhunjhunwala: {
    styleTag: 'Long-term structural growth',
    description:
      'RJ follows the Rakesh Jhunjhunwala style. He backs growing Indian companies with committed owners, adds more as the story plays out, and holds for the long run.',
  },
  'baseline-rj-rules': {
    styleTag: 'Long-term structural growth',
    description:
      'RJ Core runs the same growth-and-ownership checks as RJ, but as fixed math with no AI -- the same entry and rebalancing rules, applied the same way, every time.',
  },
};

export function getPersonaCopy(agentId: string): PersonaCopy {
  return PERSONA_COPY[agentId] || PERSONA_COPY.simons;
}
