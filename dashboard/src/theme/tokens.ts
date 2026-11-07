/**
 * Single Source of Truth (SSOT) for StockMinds Design System
 * 
 * Visual intent: Cool Vellum / Archival Stone canvas, charcoal-navy ink,
 * muted aged brass accents, mineral pine (positive alpha), and oxidized iron rust (risk/drawdown).
 * Role-differentiated surfaces instead of generic SaaS cards.
 */

import type { ForensicTag, EventSeverity } from '../types';

export const THEME_COLORS = {
  // Canvas & Surfaces (Archival Stone / Cool Vellum)
  canvas: '#F0EEE9',          // Cool vellum archival base
  surface: '#FFFFFF',         // Crisp pure white ledger panels
  surfaceSubdued: '#F6F4EF',  // Muted ledger insets and table headers
  surfaceHover: '#ECE8E0',    // Subtle row hover
  surfaceInset: '#EAE6DC',    // Sunken data wells / sparkline frames

  // Borders & Dividers
  border: '#DCD7CC',          // Primary structural hairline
  borderSubdued: '#E7E3D9',   // Light inner row dividers
  borderStrong: '#BEB7A6',    // Emphasized container borders

  // Typography Ink
  inkPrimary: '#151B26',      // Deep charcoal navy for titles and ledger figures
  inkSecondary: '#475060',    // Steely secondary slate for descriptions and labels
  inkSubdued: '#7C8698',      // Muted captions, units, and tertiary labels

  // Semantic Signals: Muted Aged Brass (Brand Accent)
  accent: '#8A7441',          // Muted aged brass
  accentHover: '#6D5B31',     // Deep bronze brass hover
  accentSubdued: '#F3EFE6',   // Brass tint container
  accentBorder: '#D6C7A1',    // Brass border

  // Semantic Signals: Mineral Pine (Profit / Positive Alpha)
  profit: '#1E6548',          // Deep mineral pine / spruce
  profitSubdued: '#EBF5F0',   // Pine tint background
  profitBorder: '#A3D4BE',    // Pine hairline border

  // Semantic Signals: Oxidized Iron Rust (Loss / Downside / Risk)
  loss: '#933835',            // Oxidized brick / iron rust
  lossSubdued: '#FBF0F0',     // Rust tint background
  lossBorder: '#E5ACAA',      // Rust hairline border

  // Architecture Layer Badges
  llmBadge: '#2A4B7C',        // Slate navy - Cognitive reasoning layer
  llmBadgeSubdued: '#EDF2F9',
  llmBadgeBorder: '#B9C9E1',

  rulesBadge: '#596373',      // Steely graphite - Control baseline
  rulesBadgeSubdued: '#F1F3F5',
  rulesBadgeBorder: '#CBD2D9',

  // Guardrail Badges
  provisional: '#8A7441',     // Aged brass warning badge (<30 closed trades)
  backtestDerived: '#5E4B7A', // Muted amethyst for historical simulation
  backtestSubdued: '#F4F0F9',
  backtestBorder: '#D3C6E5',
} as const;

export const FONT_STACKS = {
  serif: "'Newsreader', Georgia, 'Times New Roman', serif",
  sans: "'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
  mono: "'JetBrains Mono', 'SF Mono', Consolas, Menlo, monospace",
} as const;

export interface StrategyVisualConfig {
  id: string;
  name: string;
  shortName: string;
  badge: 'LLM' | 'RULES' | 'BENCHMARK';
  color: string;
  strokeDasharray?: string;
  family: string;
}

/**
 * Central configuration for all 10 strategies + Nifty 500 benchmark.
 * Differentiated by family tones:
 * - Simons (Navy indigo)
 * - Jhunjhunwala (Imperial plum)
 * - Marks (Antique bronze)
 * - Lynch (Mineral spruce)
 * - Varsity Core (Deep petrol teal)
 * - Nifty 500 (Graphite slate)
 */
export const STRATEGY_THEME: Record<string, StrategyVisualConfig> = {
  simons: {
    id: 'simons',
    name: 'Jim Simons (LLM)',
    shortName: 'Simons LLM',
    badge: 'LLM',
    color: '#1E4E8C', // Deep naval indigo
    family: 'Quant Momentum',
  },
  'baseline-simons-rules': {
    id: 'baseline-simons-rules',
    name: 'Simons (Rules Control)',
    shortName: 'Simons Rules',
    badge: 'RULES',
    color: '#406EAA',
    strokeDasharray: '4 4',
    family: 'Quant Momentum',
  },
  jhunjhunwala: {
    id: 'jhunjhunwala',
    name: 'Rakesh Jhunjhunwala (LLM)',
    shortName: 'Jhunjhunwala LLM',
    badge: 'LLM',
    color: '#65387A', // Imperial plum
    family: 'Growth & Quality',
  },
  'baseline-rj-rules': {
    id: 'baseline-rj-rules',
    name: 'Jhunjhunwala (Rules Control)',
    shortName: 'RJ Rules',
    badge: 'RULES',
    color: '#8E5FA8',
    strokeDasharray: '4 4',
    family: 'Growth & Quality',
  },
  marks: {
    id: 'marks',
    name: 'Howard Marks (LLM)',
    shortName: 'Marks LLM',
    badge: 'LLM',
    color: '#8A6520', // Antique bronze
    family: 'Contrarian Value',
  },
  'baseline-marks-rules': {
    id: 'baseline-marks-rules',
    name: 'Marks (Rules Control)',
    shortName: 'Marks Rules',
    badge: 'RULES',
    color: '#B58E45',
    strokeDasharray: '4 4',
    family: 'Contrarian Value',
  },
  lynch: {
    id: 'lynch',
    name: 'Peter Lynch (LLM)',
    shortName: 'Lynch LLM',
    badge: 'LLM',
    color: '#1E6548', // Mineral spruce
    family: 'GARP',
  },
  'baseline-lynch-rules': {
    id: 'baseline-lynch-rules',
    name: 'Lynch (Rules Control)',
    shortName: 'Lynch Rules',
    badge: 'RULES',
    color: '#3E8E6D',
    strokeDasharray: '4 4',
    family: 'GARP',
  },
  'stockminds-core': {
    id: 'stockminds-core',
    name: 'StockMinds Core (LLM)',
    shortName: 'Varsity LLM',
    badge: 'LLM',
    color: '#1C6B72', // Deep petrol teal
    family: 'Dual Confluence',
  },
  'baseline-varsity-rules': {
    id: 'baseline-varsity-rules',
    name: 'Varsity Core (Rules Control)',
    shortName: 'Varsity Rules',
    badge: 'RULES',
    color: '#3C939B',
    strokeDasharray: '4 4',
    family: 'Dual Confluence',
  },
  nifty500: {
    id: 'nifty500',
    name: 'Nifty 500 Index (Benchmark)',
    shortName: 'Nifty 500',
    badge: 'BENCHMARK',
    color: '#737B8B', // Neutral graphite slate
    strokeDasharray: '3 3',
    family: 'Passive Market Index',
  },
};

/**
 * Deterministic Forensic Tag Styles (Mineral / Oxidized aesthetic)
 */
export const FORENSIC_TAG_THEME: Record<ForensicTag, { label: string; bg: string; text: string; border: string }> = {
  WIN_MULTI_CONFLUENCE: {
    label: 'Confluence Win',
    bg: 'bg-[#EBF5F0]',
    text: 'text-[#1E6548]',
    border: 'border-[#A3D4BE]',
  },
  WIN_TREND_CONTINUATION: {
    label: 'Trend Win',
    bg: 'bg-[#E8F2F2]',
    text: 'text-[#1C6B72]',
    border: 'border-[#A1C9CD]',
  },
  WIN_CATALYST: {
    label: 'Catalyst Win',
    bg: 'bg-[#EBF5F0]',
    text: 'text-[#1E6548]',
    border: 'border-[#A3D4BE]',
  },
  LOSS_STOP_HIT: {
    label: 'Stop Loss Hit',
    bg: 'bg-[#FBF0F0]',
    text: 'text-[#933835]',
    border: 'border-[#E5ACAA]',
  },
  LOSS_REGIME_CHANGE: {
    label: 'Regime Mismatch',
    bg: 'bg-[#F9F0E9]',
    text: 'text-[#8A5A2B]',
    border: 'border-[#E2C7B3]',
  },
  LOSS_DISCIPLINE_BREACH: {
    label: 'Discipline Breach',
    bg: 'bg-[#FBF0F0]',
    text: 'text-[#933835]',
    border: 'border-[#E5ACAA]',
  },
  LOSS_VOLATILITY_EXPANSION: {
    label: 'Volatility Spike',
    bg: 'bg-[#F4F0F9]',
    text: 'text-[#5E4B7A]',
    border: 'border-[#D3C6E5]',
  },
  HOLD_PROLONGED: {
    label: 'Hold Prolonged',
    bg: 'bg-[#EDF2F9]',
    text: 'text-[#2A4B7C]',
    border: 'border-[#B9C9E1]',
  },
  NONE: {
    label: 'Normal',
    bg: 'bg-[#F6F4EF]',
    text: 'text-[#475060]',
    border: 'border-[#DCD7CC]',
  },
};

/**
 * Event Severity Styles
 */
export const SEVERITY_THEME: Record<EventSeverity, { bg: string; text: string; border: string; dot: string }> = {
  SUCCESS: {
    bg: 'bg-[#EBF5F0]',
    text: 'text-[#1E6548]',
    border: 'border-[#A3D4BE]',
    dot: 'bg-[#1E6548]',
  },
  WARNING: {
    bg: 'bg-[#F9F4EB]',
    text: 'text-[#8A7441]',
    border: 'border-[#D6C7A1]',
    dot: 'bg-[#8A7441]',
  },
  ERROR: {
    bg: 'bg-[#FBF0F0]',
    text: 'text-[#933835]',
    border: 'border-[#E5ACAA]',
    dot: 'bg-[#933835]',
  },
  INFO: {
    bg: 'bg-[#EDF2F9]',
    text: 'text-[#2A4B7C]',
    border: 'border-[#B9C9E1]',
    dot: 'bg-[#2A4B7C]',
  },
};
