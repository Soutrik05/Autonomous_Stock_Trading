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
