/**
 * Plain-English persona copy for the Agent Terminal header (Portfolio.tsx) -- a short role
 * label and a two-sentence description per agent id, with the famous investor/school name
 * broken out separately so the component can render it in green. These are NOT in the
 * backend or in any other file in the project. Review this file's text directly; it is the
 * single place this copy is defined.
 *
 * The role labels and the investor/school each description names come from the persona
 * rules already encoded in Portfolio.tsx's own PERSONA_PROFILES / getPersonaProfile (school +
 * description) and Home.tsx's SCHOOLS_OF_THOUGHT (inspiration) -- nothing here invents a
 * rule the code doesn't have:
 *  - simons: short-term statistical momentum -> "Quant trader"
 *  - lynch: GARP / quality-at-a-fair-price -> "Fair-price growth"
 *  - marks: contrarian value on cyclical distress -> "Buy the fear"
 *  - jhunjhunwala: secular domestic structural growth -> "India growth believer"
 *  - varsity/stockminds-core: Zerodha Varsity dual-confluence (solvency + trend) -> "Textbook
 *    dual influence"
 * A Rules twin gets the same role label as its LLM agent (same strategy, different execution).
 */

export interface PersonaCopy {
  /** Short underlined role label shown next to the name and LLM/Rules tag, e.g. "Quant trader". */
  roleTag: string;
  /** Plain-English description, split so the investor/school name can render in green. */
  descBefore: string;
  highlightName: string;
  descAfter: string;
}

export const PERSONA_COPY: Record<string, PersonaCopy> = {
  simons: {
    roleTag: 'Quant trader',
    descBefore: 'Jimmy follows ',
    highlightName: 'Jim Simons',
    descAfter:
      "'s style. He buys stocks that are already rising, checks that several signals agree, and sells fast when a stock turns against him.",
  },
  'baseline-simons-rules': {
    roleTag: 'Quant trader',
    descBefore: 'Jimmy Core uses the same ',
    highlightName: 'Jim Simons',
    descAfter: ' rules as Jimmy, with fixed rules and no AI.',
  },
  varsity: {
    roleTag: 'Textbook dual influence',
    descBefore: 'Varsity follows ',
    highlightName: 'Zerodha Varsity',
    descAfter:
      "'s approach. It buys financially healthy companies that are pulling back to a rising trend, and skips the trade unless both checks agree.",
  },
  'stockminds-core': {
    roleTag: 'Textbook dual influence',
    descBefore: 'StockMinds Core follows ',
    highlightName: 'Zerodha Varsity',
    descAfter:
      "'s approach. It buys financially healthy companies that are pulling back to a rising trend, and skips the trade unless both checks agree.",
  },
  'baseline-varsity-rules': {
    roleTag: 'Textbook dual influence',
    descBefore: 'Varsity Core uses the same ',
    highlightName: 'Zerodha Varsity',
    descAfter: ' rules as Varsity, with fixed rules and no AI.',
  },
  lynch: {
    roleTag: 'Fair-price growth',
    descBefore: 'Pete follows ',
    highlightName: 'Peter Lynch',
    descAfter:
      "'s style. He looks for growing companies at a fair price and holds them while the story stays strong.",
  },
  'baseline-lynch-rules': {
    roleTag: 'Fair-price growth',
    descBefore: 'Pete Core uses the same ',
    highlightName: 'Peter Lynch',
    descAfter: ' rules as Pete, with fixed rules and no AI.',
  },
  marks: {
    roleTag: 'Buy the fear',
    descBefore: 'Howie follows ',
    highlightName: 'Howard Marks',
    descAfter:
      "'s style. He buys good companies when the market is scared and waits for them to recover.",
  },
  'baseline-marks-rules': {
    roleTag: 'Buy the fear',
    descBefore: 'Howie Core uses the same ',
    highlightName: 'Howard Marks',
    descAfter: ' rules as Howie, with fixed rules and no AI.',
  },
  jhunjhunwala: {
    roleTag: 'India growth believer',
    descBefore: 'RJ follows ',
    highlightName: 'Rakesh Jhunjhunwala',
    descAfter: "'s style. He backs India's big long-term trends and adds more to winners.",
  },
  'baseline-rj-rules': {
    roleTag: 'India growth believer',
    descBefore: 'RJ Core uses the same ',
    highlightName: 'Rakesh Jhunjhunwala',
    descAfter: ' rules as RJ, with fixed rules and no AI.',
  },
};

export function getPersonaCopy(agentId: string): PersonaCopy {
  return PERSONA_COPY[agentId] || PERSONA_COPY.simons;
}
