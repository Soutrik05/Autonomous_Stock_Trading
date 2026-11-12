import type { ForensicTag, EventSeverity } from '../types';
import { FORENSIC_TAG_THEME, SEVERITY_THEME } from '../theme/tokens';

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
    return (
      d.toLocaleString('en-IN', {
        timeZone: 'Asia/Kolkata',
        year: 'numeric',
        month: 'short',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false,
      }) + ' IST'
    );
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

/**
 * Returns SSOT forensic tag metadata from theme tokens
 */
export function getForensicTagInfo(tag: ForensicTag): { label: string; bg: string; text: string; border: string } {
  return FORENSIC_TAG_THEME[tag] || FORENSIC_TAG_THEME.NONE;
}

/**
 * Returns SSOT event severity styles from theme tokens
 */
export function getSeverityStyle(severity: EventSeverity): { bg: string; text: string; border: string; dot: string } {
  return SEVERITY_THEME[severity] || SEVERITY_THEME.INFO;
}

export interface MarketSessionStatus {
  state: 'OPEN' | 'PRE_MARKET' | 'OVERNIGHT_QUEUE' | 'SETTLEMENT' | 'CLOSED_WEEKEND' | 'CLOSED_EVENING';
  label: string;
  sublabel: string;
  pillColor: 'emerald' | 'amber' | 'zinc';
  isLive: boolean;
  nextEvent: string;
}

/**
 * Returns current NSE equity market session state in Asia/Kolkata timezone
 */
export function getNSEMarketSessionStatus(date: Date = new Date()): MarketSessionStatus {
  const istFormatter = new Intl.DateTimeFormat('en-US', {
    timeZone: 'Asia/Kolkata',
    hour12: false,
    weekday: 'short',
    hour: 'numeric',
    minute: 'numeric',
  });
  const parts = istFormatter.formatToParts(date);
  const weekday = parts.find((pt) => pt.type === 'weekday')?.value || 'Mon';
  const hour = parseInt(parts.find((pt) => pt.type === 'hour')?.value || '0', 10);
  const minute = parseInt(parts.find((pt) => pt.type === 'minute')?.value || '0', 10);
  const timeMinutes = hour * 60 + minute;

  const isWeekend = weekday === 'Sat' || weekday === 'Sun';

  if (isWeekend) {
    return {
      state: 'CLOSED_WEEKEND',
      label: 'Market Closed',
      sublabel: 'Weekend Session Recess',
      pillColor: 'zinc',
      isLive: false,
      nextEvent: 'Opens Monday 09:15 IST',
    };
  }

  // 09:00 - 09:15 : Pre-market session
  if (timeMinutes >= 9 * 60 && timeMinutes < 9 * 60 + 15) {
    return {
      state: 'PRE_MARKET',
      label: 'Pre-Market Open',
      sublabel: 'Order Discovery & Matching',
      pillColor: 'amber',
      isLive: true,
      nextEvent: 'Regular Trading session opens at 09:15 IST',
    };
  }

  // 09:15 - 15:30 : Regular Trading Session
  if (timeMinutes >= 9 * 60 + 15 && timeMinutes < 15 * 60 + 30) {
    return {
      state: 'OPEN',
      label: 'Market Open',
      sublabel: 'Regular Trading Session',
      pillColor: 'emerald',
      isLive: true,
      nextEvent: 'Closes at 15:30 IST',
    };
  }

  // 15:30 - 16:00 : Settlement & Daily NAV Run
  if (timeMinutes >= 15 * 60 + 30 && timeMinutes < 16 * 60) {
    return {
      state: 'SETTLEMENT',
      label: 'Post-Market Settlement',
      sublabel: '15:35 IST NAV Computation Run',
      pillColor: 'amber',
      isLive: false,
      nextEvent: 'Nightly Strategy Runner passes at 22:00 IST',
    };
  }

  // 22:00 to 09:00 next day : Overnight Pending Queue
  if (timeMinutes >= 22 * 60 || timeMinutes < 9 * 60) {
    return {
      state: 'OVERNIGHT_QUEUE',
      label: 'Overnight Queue',
      sublabel: 'Orders Queued for Market Open',
      pillColor: 'amber',
      isLive: true,
      nextEvent: 'Execution engine dispatches at 09:15 IST',
    };
  }

  // 16:00 to 22:00 : Evening Market Closed
  return {
    state: 'CLOSED_EVENING',
    label: 'Market Closed',
    sublabel: 'Evening Session Intermission',
    pillColor: 'zinc',
    isLive: false,
    nextEvent: 'Nightly Agent Runner executes at 22:00 IST',
  };
}

