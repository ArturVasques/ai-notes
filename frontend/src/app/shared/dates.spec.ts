import {
  addMonths,
  currentMonth,
  formatDayLabel,
  formatMonth,
  monthBounds,
  monthKey,
  todayIso,
} from './dates';

describe('dates', () => {
  const now = new Date(2026, 8, 25); // 25 September 2026

  it('formats today as an ISO date in local time', () => {
    expect(todayIso(now)).toBe('2026-09-25');
  });

  it('computes month bounds including February', () => {
    expect(monthBounds({ year: 2026, month: 9 })).toEqual({ from: '2026-09-01', to: '2026-09-30' });
    expect(monthBounds({ year: 2028, month: 2 })).toEqual({ from: '2028-02-01', to: '2028-02-29' });
  });

  it('moves across years', () => {
    expect(addMonths({ year: 2026, month: 1 }, -1)).toEqual({ year: 2025, month: 12 });
    expect(addMonths({ year: 2026, month: 12 }, 1)).toEqual({ year: 2027, month: 1 });
    expect(monthKey(addMonths(currentMonth(now), 0))).toBe('2026-09');
  });

  it('labels months and days', () => {
    expect(formatMonth({ year: 2026, month: 9 })).toBe('September 2026');
    expect(formatDayLabel('2026-09-25', now)).toBe('Today');
    expect(formatDayLabel('2026-09-24', now)).toBe('Yesterday');
    expect(formatDayLabel('2026-09-10', now)).toBe('Thu 10 Sept');
    expect(formatDayLabel('2025-12-31', now)).toBe('31 Dec 2025');
  });
});
