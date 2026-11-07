/**
 * Single Source of Truth (SSOT) for StockMinds Design System
 * 
 * Changing any token here updates all components, charts, and pages across the application.
 */

import type { ForensicTag, EventSeverity } from '../types';

export const THEME_COLORS = {
  // Canvas & Surfaces
  canvas: '#FAF9F6',          // Warm porcelain base background
  surface: '#FFFFFF',         // Pure white cards and panels
  surfaceSubdued: '#F4F2EC',  // Insets, table headers, and pill backgrounds
  surfaceHover: '#F7F5EE',    // Hover state for rows and cards

  // Borders & Dividers
  border: '#E5E2D9',          // Crisp warm border
  borderSubdued: '#EDEAE2',   // Subtle dividers and gridlines
  borderHover: '#D5D0C3',     // Border on hover / focus

  // Typography Ink
  inkPrimary: '#111827',      // Deep slate black for titles and data
  inkSecondary: '#4B5563',    // Neutral slate for descriptions and labels
  inkSubdued: '#9CA3AF',      // Muted captions and tertiary indicators

  // Semantic Financial Signals
  accent: '#D97706',          // Amber Gold - Academic brand accent
  accentHover: '#B45309',     // Amber dark hover
  accentSubdued: '#FEF3C7',   // Amber light pill background
  
  profit: '#059669',          // Emerald Green - Positive return & alpha
  profitSubdued: '#ECFDF5',   // Light emerald badge background
  profitBorder: '#A7F3D0',    // Emerald border

  loss: '#DC2626',            // Crimson Red - Negative return, stop hit
  lossSubdued: '#FEF2F2',     // Light crimson badge background
  lossBorder: '#FECACA',      // Crimson border

  // Strategy Badges
  llmBadge: '#2563EB',        // Royal Blue - Cognitive LLM layer
  llmBadgeSubdued: '#EFF6FF', 
  llmBadgeBorder: '#BFDBFE',

  rulesBadge: '#475569',      // Slate Gray - Control rules baseline
  rulesBadgeSubdued: '#F1F5F9',
  rulesBadgeBorder: '#CBD5E1',

  // Guardrail Badges
  provisional: '#D97706',     // Amber alert (<30 closed trades)
  backtestDerived: '#7C3AED', // Purple isolation badge for simulations
  backtestSubdued: '#F5F3FF',
  backtestBorder: '#DDD6FE',
} as const;

export const FONT_STACKS = {
  serif: "'Newsreader', 'Crimson Pro', Georgia, serif",
  sans: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
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
 * Changing a color or label here updates Recharts lines, legends, and table chips simultaneously.
 */
export const STRATEGY_THEME: Record<string, StrategyVisualConfig> = {
  simons: {
    id: 'simons',
    name: 'Jim Simons (LLM)',
    shortName: 'Simons LLM',
    badge: 'LLM',
    color: '#2563EB', // Blue
    family: 'Quant Momentum',
  },
  'baseline-simons-rules': {
    id: 'baseline-simons-rules',
    name: 'Simons (Rules Control)',
    shortName: 'Simons Rules',
    badge: 'RULES',
    color: '#3B82F6',
    strokeDasharray: '4 4',
    family: 'Quant Momentum',
  },
  jhunjhunwala: {
    id: 'jhunjhunwala',
    name: 'Rakesh Jhunjhunwala (LLM)',
    shortName: 'Jhunjhunwala LLM',
    badge: 'LLM',
    color: '#7C3AED', // Purple
    family: 'Growth & Quality',
  },
  'baseline-rj-rules': {
    id: 'baseline-rj-rules',
    name: 'Jhunjhunwala (Rules Control)',
    shortName: 'RJ Rules',
    badge: 'RULES',
    color: '#8B5CF6',
    strokeDasharray: '4 4',
    family: 'Growth & Quality',
  },
  marks: {
    id: 'marks',
    name: 'Howard Marks (LLM)',
    shortName: 'Marks LLM',
    badge: 'LLM',
    color: '#D97706', // Amber
    family: 'Contrarian Value',
  },
  'baseline-marks-rules': {
    id: 'baseline-marks-rules',
    name: 'Marks (Rules Control)',
    shortName: 'Marks Rules',
    badge: 'RULES',
    color: '#F59E0B',
    strokeDasharray: '4 4',
    family: 'Contrarian Value',
  },
  lynch: {
    id: 'lynch',
    name: 'Peter Lynch (LLM)',
    shortName: 'Lynch LLM',
    badge: 'LLM',
    color: '#059669', // Emerald
    family: 'GARP',
  },
  'baseline-lynch-rules': {
    id: 'baseline-lynch-rules',
    name: 'Lynch (Rules Control)',
    shortName: 'Lynch Rules',
    badge: 'RULES',
    color: '#10B981',
    strokeDasharray: '4 4',
    family: 'GARP',
  },
  'stockminds-core': {
    id: 'stockminds-core',
    name: 'StockMinds Core (LLM)',
    shortName: 'Varsity LLM',
    badge: 'LLM',
    color: '#0891B2', // Cyan
    family: 'Dual Confluence',
  },
  'baseline-varsity-rules': {
    id: 'baseline-varsity-rules',
    name: 'Varsity Core (Rules Control)',
    shortName: 'Varsity Rules',
    badge: 'RULES',
    color: '#06B6D4',
    strokeDasharray: '4 4',
    family: 'Dual Confluence',
  },
  nifty500: {
    id: 'nifty500',
    name: 'Nifty 500 Index (Benchmark)',
    shortName: 'Nifty 500',
    badge: 'BENCHMARK',
    color: '#64748B', // Neutral Slate
    strokeDasharray: '2 2',
    family: 'Passive Market Index',
  },
};

/**
 * Deterministic Forensic Tag Styles
 */
export const FORENSIC_TAG_THEME: Record<ForensicTag, { label: string; bg: string; text: string; border: string }> = {
  WIN_MULTI_CONFLUENCE: {
    label: 'Confluence Win',
    bg: 'bg-emerald-50',
    text: 'text-emerald-800',
    border: 'border-emerald-200',
  },
  WIN_TREND_CONTINUATION: {
    label: 'Trend Win',
    bg: 'bg-teal-50',
    text: 'text-teal-800',
    border: 'border-teal-200',
  },
  WIN_CATALYST: {
    label: 'Catalyst Win',
    bg: 'bg-green-50',
    text: 'text-green-800',
    border: 'border-green-200',
  },
  LOSS_STOP_HIT: {
    label: 'Stop Loss Hit',
    bg: 'bg-amber-50',
    text: 'text-amber-800',
    border: 'border-amber-200',
  },
  LOSS_REGIME_CHANGE: {
    label: 'Regime Mismatch',
    bg: 'bg-orange-50',
    text: 'text-orange-800',
    border: 'border-orange-200',
  },
  LOSS_DISCIPLINE_BREACH: {
    label: 'Discipline Breach',
    bg: 'bg-rose-50',
    text: 'text-rose-800',
    border: 'border-rose-200',
  },
  LOSS_VOLATILITY_EXPANSION: {
    label: 'Volatility Spike',
    bg: 'bg-purple-50',
    text: 'text-purple-800',
    border: 'border-purple-200',
  },
  HOLD_PROLONGED: {
    label: 'Hold Prolonged',
    bg: 'bg-blue-50',
    text: 'text-blue-800',
    border: 'border-blue-200',
  },
  NONE: {
    label: 'Normal',
    bg: 'bg-stone-100',
    text: 'text-stone-700',
    border: 'border-stone-200',
  },
};

/**
 * Event Severity Styles
 */
export const SEVERITY_THEME: Record<EventSeverity, { bg: string; text: string; border: string; dot: string }> = {
  SUCCESS: {
    bg: 'bg-emerald-50',
    text: 'text-emerald-800',
    border: 'border-emerald-200',
    dot: 'bg-emerald-500',
  },
  WARNING: {
    bg: 'bg-amber-50',
    text: 'text-amber-800',
    border: 'border-amber-200',
    dot: 'bg-amber-500',
  },
  ERROR: {
    bg: 'bg-rose-50',
    text: 'text-rose-800',
    border: 'border-rose-200',
    dot: 'bg-rose-500',
  },
  INFO: {
    bg: 'bg-blue-50',
    text: 'text-blue-800',
    border: 'border-blue-200',
    dot: 'bg-blue-500',
  },
};
