import { describe, expect, it } from 'vitest';
import { isMarketOpen, getNextOpen, getNextClose, NSE_HOLIDAYS } from './marketHours';

// All instants below are given as UTC ISO strings; the comment on each states the
// equivalent Asia/Kolkata (IST, UTC+5:30) wall-clock time that isMarketOpen must use.

describe('isMarketOpen', () => {
  it('is open on a weekday within trading hours', () => {
    // 2026-11-17 is a Tuesday. 10:00 IST = 04:30 UTC.
    expect(isMarketOpen(new Date('2026-11-17T04:30:00Z'))).toBe(true);
  });

  it('is closed on a weekday before 09:15 IST', () => {
    // 09:14:59 IST = 03:44:59 UTC.
    expect(isMarketOpen(new Date('2026-11-17T03:44:59Z'))).toBe(false);
  });

  it('is open at exactly 09:15:00 IST (inclusive start)', () => {
    // 09:15:00 IST = 03:45:00 UTC.
    expect(isMarketOpen(new Date('2026-11-17T03:45:00Z'))).toBe(true);
  });

  it('is closed at exactly 15:30:00 IST (exclusive end)', () => {
    // 15:30:00 IST = 10:00:00 UTC.
    expect(isMarketOpen(new Date('2026-11-17T10:00:00Z'))).toBe(false);
  });

  it('is closed on Saturday even during would-be trading hours', () => {
    // 2026-11-21 is a Saturday. 10:00 IST = 04:30 UTC.
    expect(isMarketOpen(new Date('2026-11-21T04:30:00Z'))).toBe(false);
  });

  it('is closed on Sunday even during would-be trading hours', () => {
    // 2026-11-15 is a Sunday. 10:00 IST = 04:30 UTC.
    expect(isMarketOpen(new Date('2026-11-15T04:30:00Z'))).toBe(false);
  });

  it('is closed on a date listed in NSE_HOLIDAYS', () => {
    // 2026-11-17 is a trading weekday at 10:00 IST; add it as a holiday and confirm
    // the holiday list overrides the weekday/time check. Restored after the assertion
    // so this test doesn't leak state into the others.
    NSE_HOLIDAYS.push('2026-11-17');
    try {
      expect(isMarketOpen(new Date('2026-11-17T04:30:00Z'))).toBe(false);
    } finally {
      NSE_HOLIDAYS.pop();
    }
  });

  it('uses the IST weekday, not the UTC weekday, across the day-rollover boundary', () => {
    // 2026-11-15 20:00 UTC is a Sunday in UTC, but +5:30 rolls it to
    // 2026-11-16 01:30 IST -- a Monday. A implementation that read the weekday from
    // the raw UTC/local date (Sunday) instead of the IST conversion would still reach
    // the same "closed" conclusion here only by the coincidence that 01:30 is also
    // before market open, so this is paired with the next test, which cannot be
    // explained by a UTC-vs-IST weekday mixup at all.
    expect(isMarketOpen(new Date('2026-11-15T20:00:00Z'))).toBe(false);
  });

  it('is open when the IST time is within hours even though the raw UTC clock time is not', () => {
    // 2026-11-16 is a Monday. 05:00 UTC on that date is still 05:00 by the UTC clock
    // (well before 09:15), but the correct IST conversion is 10:30 IST -- inside
    // trading hours. A version of isMarketOpen that forgot to convert to Asia/Kolkata
    // (e.g. used the Date's own local/UTC hour and minute directly) would compute
    // 05:00 and wrongly report the market closed; only a correct timeZone conversion
    // produces 10:30 and reports it open. This is the proof that IST, not the host's
    // time zone, drives the result.
    expect(isMarketOpen(new Date('2026-11-16T05:00:00Z'))).toBe(true);
  });
});

describe('getNextClose', () => {
  it('open at 11:42 IST -> next close is 15:30 the same day', () => {
    // 2026-11-17 is a Tuesday. 11:42 IST = 06:12 UTC.
    const next = getNextClose(new Date('2026-11-17T06:12:00Z'));
    expect(next.toISOString()).toBe(new Date('2026-11-17T10:00:00Z').toISOString());
  });

  it('after hours -> next close is the next trading day\'s 15:30', () => {
    // 2026-11-17 (Tue) 20:00 IST = 14:30 UTC -> next trading day is Wed 2026-11-18, close 15:30 IST = 10:00 UTC.
    const next = getNextClose(new Date('2026-11-17T14:30:00Z'));
    expect(next.toISOString()).toBe(new Date('2026-11-18T10:00:00Z').toISOString());
  });
});

describe('getNextOpen', () => {
  it('before 09:15 on a trading day -> next open is today 09:15', () => {
    // 2026-11-17 (Tue) 08:00 IST = 02:30 UTC.
    const next = getNextOpen(new Date('2026-11-17T02:30:00Z'));
    expect(next.toISOString()).toBe(new Date('2026-11-17T03:45:00Z').toISOString());
  });

  it('Friday 16:00 IST -> next open is Monday 09:15', () => {
    // 2026-11-20 is a Friday. 16:00 IST = 10:30 UTC.
    const next = getNextOpen(new Date('2026-11-20T10:30:00Z'));
    // 2026-11-23 is the following Monday. 09:15 IST = 03:45 UTC.
    expect(next.toISOString()).toBe(new Date('2026-11-23T03:45:00Z').toISOString());
  });

  it('skips a holiday that falls on the otherwise-next trading day', () => {
    // Same Friday-16:00 instant as above, but Monday 2026-11-23 is now a holiday,
    // so the next open should fall through to Tuesday 2026-11-24 instead.
    NSE_HOLIDAYS.push('2026-11-23');
    try {
      const next = getNextOpen(new Date('2026-11-20T10:30:00Z'));
      expect(next.toISOString()).toBe(new Date('2026-11-24T03:45:00Z').toISOString());
    } finally {
      NSE_HOLIDAYS.pop();
    }
  });
});
