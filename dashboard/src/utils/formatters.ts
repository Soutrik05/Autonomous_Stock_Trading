import type { ForensicTag, EventSeverity } from '../types';

/**
 * Converts integer paise into standard Indian Rupee string formatting (₹ X,XX,XXX.XX)
 */
export function formatPaiseToRupees(paise: number | undefined | null): string {
  if (paise === undefined || paise === null || isNaN(paise)) return '₹0.00';
  const rupees = paise / 100;
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 2,
    minimumFractionDigits: 2,
  }).format(rupees);
}

/**
 * Compact Indian currency representation (e.g. ₹10.02 L, ₹1.45 Cr)
 */
export function formatPaiseCompact(paise: number | undefined | null): string {
  if (paise === undefined || paise === null || isNaN(paise)) return '₹0';
  const rupees = Math.abs(paise / 100);
  const sign = paise < 0 ? '-' : '';

  if (rupees >= 10000000) {
    return `${sign}₹${(rupees / 10000000).toFixed(2)} Cr`;
  }
  if (rupees >= 100000) {
    return `${sign}₹${(rupees / 100000).toFixed(2)} L`;
  }
  if (rupees >= 1000) {
    return `${sign}₹${(rupees / 1000).toFixed(1)} k`;
  }
  return `${sign}₹${rupees.toFixed(2)}`;
}

/**
 * Formats a percentage with optional +/- sign
 */
export function formatPct(val: number | undefined | null, includeSign = true): string {
  if (val === undefined || val === null || isNaN(val)) return '0.00%';
  const prefix = includeSign && val > 0 ? '+' : '';
  return `${prefix}${val.toFixed(2)}%`;
}

/**
 * Formats an ISO string into IST readable timestamp
 */
export function formatISTDateTime(iso: string | undefined | null): string {
  if (!iso) return '-';
  try {
    const d = new Date(iso);
    return d.toLocaleString('en-IN', {
      timeZone: 'Asia/Kolkata',
      year: 'numeric',
      month: 'short',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    }) + ' IST';
  } catch {
    return iso;
  }
}

export function formatISTDate(iso: string | undefined | null): string {
  if (!iso) return '-';
  try {
    const d = new Date(iso);
    return d.toLocaleDateString('en-IN', {
      timeZone: 'Asia/Kolkata',
      year: 'numeric',
      month: 'short',
      day: '2-digit',
    });
  } catch {
    return iso;
  }
}

export function getForensicTagInfo(tag: ForensicTag): { label: string; bg: string; text: string } {
  switch (tag) {
    case 'WIN_MULTI_CONFLUENCE':
      return { label: 'Confluence Win', bg: 'bg-emerald-100 dark:bg-emerald-950/40', text: 'text-emerald-800 dark:text-emerald-300' };
    case 'WIN_TREND_CONTINUATION':
      return { label: 'Trend Win', bg: 'bg-teal-100 dark:bg-teal-950/40', text: 'text-teal-800 dark:text-teal-300' };
    case 'WIN_CATALYST':
      return { label: 'Catalyst Win', bg: 'bg-green-100 dark:bg-green-950/40', text: 'text-green-800 dark:text-green-300' };
    case 'LOSS_STOP_HIT':
      return { label: 'Stop Loss Hit', bg: 'bg-amber-100 dark:bg-amber-950/40', text: 'text-amber-800 dark:text-amber-300' };
    case 'LOSS_REGIME_CHANGE':
      return { label: 'Regime Change', bg: 'bg-orange-100 dark:bg-orange-950/40', text: 'text-orange-800 dark:text-orange-300' };
    case 'LOSS_DISCIPLINE_BREACH':
      return { label: 'Discipline Breach', bg: 'bg-red-100 dark:bg-red-950/40', text: 'text-red-800 dark:text-red-300' };
    case 'LOSS_VOLATILITY_EXPANSION':
      return { label: 'Volatility Spike', bg: 'bg-purple-100 dark:bg-purple-950/40', text: 'text-purple-800 dark:text-purple-300' };
    case 'HOLD_PROLONGED':
      return { label: 'Hold Prolonged', bg: 'bg-blue-100 dark:bg-blue-950/40', text: 'text-blue-800 dark:text-blue-300' };
    default:
      return { label: 'Normal', bg: 'bg-slate-100 dark:bg-slate-800', text: 'text-slate-700 dark:text-slate-300' };
  }
}

export function getSeverityStyle(severity: EventSeverity): { bg: string; text: string; dot: string } {
  switch (severity) {
    case 'SUCCESS':
      return { bg: 'bg-emerald-50 dark:bg-emerald-950/20', text: 'text-emerald-700 dark:text-emerald-300', dot: 'bg-emerald-500' };
    case 'WARNING':
      return { bg: 'bg-amber-50 dark:bg-amber-950/20', text: 'text-amber-700 dark:text-amber-300', dot: 'bg-amber-500' };
    case 'ERROR':
      return { bg: 'bg-rose-50 dark:bg-rose-950/20', text: 'text-rose-700 dark:text-rose-300', dot: 'bg-rose-500' };
    case 'INFO':
    default:
      return { bg: 'bg-blue-50 dark:bg-blue-950/20', text: 'text-blue-700 dark:text-blue-300', dot: 'bg-blue-500' };
  }
}
