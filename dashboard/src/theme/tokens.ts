/**
 * Single Source of Truth (SSOT) for StockMinds Design System
 * 
 * Visual intent: OpenRouter-inspired Deep Obsidian Arena, translucent glassmorphic panels,
 * razor-sharp micro-borders, electric cyan/cobalt accents, and vivid telemetry signals.
 */

import type { ForensicTag, EventSeverity } from '../types';

export const THEME_COLORS = {
  // Canvas & Surfaces (Institutional Obsidian Slate)
  canvas: '#090B10',                          // Deep matte obsidian
  surface: 'rgba(16, 20, 29, 0.75)',         // Matte institutional slate glass
  surfaceSubdued: 'rgba(255, 255, 255, 0.025)',// Data wells & table headers
  surfaceHover: 'rgba(255, 255, 255, 0.05)',  // Micro hover
  surfaceInset: 'rgba(0, 0, 0, 0.4)',         // Recessed wells

  // Borders & Hairlines
  border: 'rgba(255, 255, 255, 0.08)',       // Structural micro-border
  borderSubdued: 'rgba(255, 255, 255, 0.04)',  // Inner dividers
  borderStrong: 'rgba(255, 255, 255, 0.16)',   // Focused / active border

  // Typography Ink
  inkPrimary: '#FFFFFF',                      // Solid high-contrast white
  inkSecondary: '#94A3B8',                    // Steely slate secondary
  inkSubdued: '#64748B',                      // Muted tertiary & units

  // Semantic Signals: Institutional Cobalt (Brand Accent)
  accent: '#2563EB',                          // Institutional royal cobalt
  accentHover: '#1D4ED8',                     // Deepened cobalt hover
  accentSubdued: 'rgba(37, 99, 235, 0.10)',   // Subtle cobalt background
  accentBorder: 'rgba(37, 99, 235, 0.30)',   // Subtle cobalt border

  // Semantic Signals: Tabular Emerald (Profit / Positive Alpha)
  profit: '#10B981',                          // Muted crisp emerald
  profitSubdued: 'rgba(16, 185, 129, 0.10)',  // Emerald background tint
  profitBorder: 'rgba(16, 185, 129, 0.25)',   // Emerald border

  // Semantic Signals: Tabular Crimson (Loss / Drawdown)
  loss: '#EF4444',                            // Crisp tabular crimson
  lossSubdued: 'rgba(239, 68, 68, 0.10)',     // Crimson background tint
  lossBorder: 'rgba(239, 68, 68, 0.25)',      // Crimson border

  // Architecture Layer Badges
  llmBadge: '#3B82F6',                        // Cobalt blue for LLM
  llmBadgeSubdued: 'rgba(59, 130, 246, 0.10)',
  llmBadgeBorder: 'rgba(59, 130, 246, 0.25)',

  rulesBadge: '#64748B',                      // Slate for Rules controls
  rulesBadgeSubdued: 'rgba(100, 116, 139, 0.10)',
  rulesBadgeBorder: 'rgba(100, 116, 139, 0.25)',

  // Guardrail Badges
  provisional: '#F59E0B',                     // Amber alert (<30 closed trades)
  backtestDerived: '#8B5CF6',                 // Violet for backtest simulation
  backtestSubdued: 'rgba(139, 92, 246, 0.10)',
  backtestBorder: 'rgba(139, 92, 246, 0.25)',
} as const;

export const FONT_STACKS = {
  sans: "'Plus Jakarta Sans', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
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
 * Central configuration for all 10 strategies + Nifty 500 benchmark in Obsidian Arena.
 */
export const STRATEGY_THEME: Record<string, StrategyVisualConfig> = {
  simons: {
    id: 'simons',
    name: 'Jim Simons (LLM)',
    shortName: 'Simons LLM',
    badge: 'LLM',
    color: '#3B82F6', // Electric Blue
    family: 'Quant Momentum',
  },
  'baseline-simons-rules': {
    id: 'baseline-simons-rules',
    name: 'Simons (Rules Control)',
    shortName: 'Simons Rules',
    badge: 'RULES',
    color: '#60A5FA',
    strokeDasharray: '4 4',
    family: 'Quant Momentum',
  },
  jhunjhunwala: {
    id: 'jhunjhunwala',
    name: 'Rakesh Jhunjhunwala (LLM)',
    shortName: 'Jhunjhunwala LLM',
    badge: 'LLM',
    color: '#A855F7', // Neon Purple
    family: 'Growth & Quality',
  },
  'baseline-rj-rules': {
    id: 'baseline-rj-rules',
    name: 'Jhunjhunwala (Rules Control)',
    shortName: 'RJ Rules',
    badge: 'RULES',
    color: '#C084FC',
    strokeDasharray: '4 4',
    family: 'Growth & Quality',
  },
  marks: {
    id: 'marks',
    name: 'Howard Marks (LLM)',
    shortName: 'Marks LLM',
    badge: 'LLM',
    color: '#F59E0B', // Amber Gold
    family: 'Contrarian Value',
  },
  'baseline-marks-rules': {
    id: 'baseline-marks-rules',
    name: 'Marks (Rules Control)',
    shortName: 'Marks Rules',
    badge: 'RULES',
    color: '#FBBF24',
    strokeDasharray: '4 4',
    family: 'Contrarian Value',
  },
  lynch: {
    id: 'lynch',
    name: 'Peter Lynch (LLM)',
    shortName: 'Lynch LLM',
    badge: 'LLM',
    color: '#10B981', // Vivid Emerald
    family: 'GARP',
  },
  'baseline-lynch-rules': {
    id: 'baseline-lynch-rules',
    name: 'Lynch (Rules Control)',
    shortName: 'Lynch Rules',
    badge: 'RULES',
    color: '#34D399',
    strokeDasharray: '4 4',
    family: 'GARP',
  },
  'stockminds-core': {
    id: 'stockminds-core',
    name: 'StockMinds Core (LLM)',
    shortName: 'Varsity LLM',
    badge: 'LLM',
    color: '#0284C7', // Deep Sky Blue
    family: 'Dual Confluence',
  },
  'baseline-varsity-rules': {
    id: 'baseline-varsity-rules',
    name: 'Varsity Core (Rules Control)',
    shortName: 'Varsity Rules',
    badge: 'RULES',
    color: '#38BDF8',
    strokeDasharray: '4 4',
    family: 'Dual Confluence',
  },
  nifty500: {
    id: 'nifty500',
    name: 'Nifty 500 Index (Benchmark)',
    shortName: 'Nifty 500',
    badge: 'BENCHMARK',
    color: '#94A3B8', // Neutral Silver Slate
    strokeDasharray: '3 3',
    family: 'Passive Market Index',
  },
};

/**
 * Deterministic Forensic Tag Styles for Dark Glass Arena
 */
export const FORENSIC_TAG_THEME: Record<ForensicTag, { label: string; bg: string; text: string; border: string }> = {
  WIN_MULTI_CONFLUENCE: {
    label: 'Confluence Win',
    bg: 'bg-emerald-500/10',
    text: 'text-emerald-400',
    border: 'border-emerald-500/30',
  },
  WIN_TREND_CONTINUATION: {
    label: 'Trend Win',
    bg: 'bg-blue-500/10',
    text: 'text-blue-400',
    border: 'border-blue-500/30',
  },
  WIN_CATALYST: {
    label: 'Catalyst Win',
    bg: 'bg-teal-500/10',
    text: 'text-teal-400',
    border: 'border-teal-500/30',
  },
  LOSS_STOP_HIT: {
    label: 'Stop Loss Hit',
    bg: 'bg-rose-500/10',
    text: 'text-rose-400',
    border: 'border-rose-500/30',
  },
  LOSS_REGIME_CHANGE: {
    label: 'Regime Mismatch',
    bg: 'bg-amber-500/10',
    text: 'text-amber-400',
    border: 'border-amber-500/30',
  },
  LOSS_DISCIPLINE_BREACH: {
    label: 'Discipline Breach',
    bg: 'bg-rose-500/15',
    text: 'text-rose-300',
    border: 'border-rose-500/40',
  },
  LOSS_VOLATILITY_EXPANSION: {
    label: 'Volatility Spike',
    bg: 'bg-purple-500/10',
    text: 'text-purple-400',
    border: 'border-purple-500/30',
  },
  HOLD_PROLONGED: {
    label: 'Hold Prolonged',
    bg: 'bg-blue-500/10',
    text: 'text-blue-400',
    border: 'border-blue-500/30',
  },
  NONE: {
    label: 'Normal',
    bg: 'bg-white/5',
    text: 'text-slate-400',
    border: 'border-white/10',
  },
};

/**
 * Event Severity Styles
 */
export const SEVERITY_THEME: Record<EventSeverity, { bg: string; text: string; border: string; dot: string }> = {
  SUCCESS: {
    bg: 'bg-emerald-500/10',
    text: 'text-emerald-400',
    border: 'border-emerald-500/30',
    dot: 'bg-emerald-400',
  },
  WARNING: {
    bg: 'bg-amber-500/10',
    text: 'text-amber-400',
    border: 'border-amber-500/30',
    dot: 'bg-amber-400',
  },
  ERROR: {
    bg: 'bg-rose-500/10',
    text: 'text-rose-400',
    border: 'border-rose-500/30',
    dot: 'bg-rose-400',
  },
  INFO: {
    bg: 'bg-blue-500/10',
    text: 'text-blue-400',
    border: 'border-blue-500/30',
    dot: 'bg-blue-400',
  },
};
