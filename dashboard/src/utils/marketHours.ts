import { useEffect, useState } from 'react';

/**
 * Add "YYYY-MM-DD" (IST calendar date) entries here as NSE holidays are announced.
 * If today's IST date is in this list, the market is treated as closed regardless
 * of the day of week or time.
 */
export const NSE_HOLIDAYS: string[] = [];

const MARKET_OPEN_MINUTES = 9 * 60 + 15; // 09:15
const MARKET_CLOSE_MINUTES = 15 * 60 + 30; // 15:30

const TRADING_WEEKDAYS = new Set(['Mon', 'Tue', 'Wed', 'Thu', 'Fri']);

const IST_FORMATTER = new Intl.DateTimeFormat('en-US', {
  timeZone: 'Asia/Kolkata',
  weekday: 'short',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hour12: false,
});

interface ISTParts {
  weekday: string;
  dateKey: string;
  minutesSinceMidnight: number;
}

function getISTParts(now: Date): ISTParts {
  const map: Record<string, string> = {};
  for (const part of IST_FORMATTER.formatToParts(now)) {
    if (part.type !== 'literal') map[part.type] = part.value;
  }
  // With hour12:false, Intl can report midnight as "24" instead of "00".
  const hour = Number(map.hour) % 24;
  const minute = Number(map.minute);
  const second = Number(map.second);
  return {
    weekday: map.weekday,
    dateKey: `${map.year}-${map.month}-${map.day}`,
    minutesSinceMidnight: hour * 60 + minute + second / 60,
  };
}

/**
 * Manual override for local testing/screenshots, since the real market state depends
 * on wall-clock time and can't otherwise be forced to a chosen value. A URL param
 * (?market=open or ?market=closed) takes priority; failing that, a localStorage key
 * ("stockminds_market_override") set to "open" or "closed" is used instead. Reading
 * window.location/localStorage is wrapped in try/catch because it can throw (SSR,
 * privacy mode, disabled storage) and a thrown error here must never break the header.
 */
function getOverride(): 'open' | 'closed' | null {
  try {
    const fromUrl = new URLSearchParams(window.location.search).get('market');
    if (fromUrl === 'open' || fromUrl === 'closed') return fromUrl;
  } catch {
    // ignore - fall through to localStorage / real market hours
  }
  try {
    const stored = window.localStorage.getItem('stockminds_market_override');
    if (stored === 'open' || stored === 'closed') return stored;
  } catch {
    // ignore - fall through to real market hours
  }
  return null;
}

/**
 * NSE market hours: Monday-Friday, 09:15:00 up to (but not including) 15:30:00 IST.
 * Always resolved via Intl.DateTimeFormat with timeZone: 'Asia/Kolkata' so the result
 * is correct regardless of the browser's own local time zone.
 */
export function isMarketOpen(now: Date = new Date()): boolean {
  const override = getOverride();
  if (override) return override === 'open';

  const ist = getISTParts(now);
  if (!TRADING_WEEKDAYS.has(ist.weekday)) return false;
  if (NSE_HOLIDAYS.includes(ist.dateKey)) return false;

  return ist.minutesSinceMidnight >= MARKET_OPEN_MINUTES && ist.minutesSinceMidnight < MARKET_CLOSE_MINUTES;
}

/** Re-checks market status every 15 seconds; cleans up its timer on unmount. */
export function useMarketOpen(): boolean {
  const [open, setOpen] = useState(() => isMarketOpen());

  useEffect(() => {
    const interval = setInterval(() => setOpen(isMarketOpen()), 15000);
    return () => clearInterval(interval);
  }, []);

  return open;
}

function istPartsOf(date: Date): { year: number; month: number; day: number; hour: number; minute: number; second: number; weekday: string } {
  const map: Record<string, string> = {};
  for (const part of IST_FORMATTER.formatToParts(date)) {
    if (part.type !== 'literal') map[part.type] = part.value;
  }
  return {
    year: Number(map.year),
    month: Number(map.month),
    day: Number(map.day),
    hour: Number(map.hour) % 24,
    minute: Number(map.minute),
    second: Number(map.second),
    weekday: map.weekday,
  };
}

/** The UTC instant corresponding to a given IST (Asia/Kolkata) wall-clock date and time. */
function istToUtc(year: number, month: number, day: number, hour: number, minute: number, second = 0): Date {
  const IST_OFFSET_MINUTES = 5 * 60 + 30;
  return new Date(Date.UTC(year, month - 1, day, hour, minute, second) - IST_OFFSET_MINUTES * 60000);
}

function isTradingDay(year: number, month: number, day: number, weekday: string): boolean {
  if (!TRADING_WEEKDAYS.has(weekday)) return false;
  const dateKey = `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
  return !NSE_HOLIDAYS.includes(dateKey);
}

/**
 * The next instant the market opens (09:15 IST on the next trading day, today included if
 * it's still before 09:15 on a trading day). Weekends and NSE_HOLIDAYS are skipped.
 */
export function getNextOpen(now: Date = new Date()): Date {
  const ist = istPartsOf(now);
  const minutesNow = ist.hour * 60 + ist.minute + ist.second / 60;

  if (isTradingDay(ist.year, ist.month, ist.day, ist.weekday) && minutesNow < MARKET_OPEN_MINUTES) {
    return istToUtc(ist.year, ist.month, ist.day, 9, 15);
  }

  let candidate = istToUtc(ist.year, ist.month, ist.day, 9, 15);
  for (let i = 0; i < 14; i++) {
    candidate = new Date(candidate.getTime() + 24 * 60 * 60 * 1000);
    const parts = istPartsOf(candidate);
    if (isTradingDay(parts.year, parts.month, parts.day, parts.weekday)) {
      return istToUtc(parts.year, parts.month, parts.day, 9, 15);
    }
  }
  return candidate;
}

/**
 * The next instant the market closes (15:30 IST): later today if the market is still open
 * today, otherwise the close of the next trading day's session.
 */
export function getNextClose(now: Date = new Date()): Date {
  const ist = istPartsOf(now);
  const minutesNow = ist.hour * 60 + ist.minute + ist.second / 60;

  if (isTradingDay(ist.year, ist.month, ist.day, ist.weekday) && minutesNow < MARKET_CLOSE_MINUTES) {
    return istToUtc(ist.year, ist.month, ist.day, 15, 30);
  }

  const nextOpen = getNextOpen(now);
  const parts = istPartsOf(nextOpen);
  return istToUtc(parts.year, parts.month, parts.day, 15, 30);
}
