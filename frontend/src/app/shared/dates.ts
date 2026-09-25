/**
 * Date helpers. The API works with calendar dates (`YYYY-MM-DD`), never
 * timestamps, so everything here stays in local calendar terms.
 */

export interface MonthRef {
  year: number;
  month: number; // 1-12
}

export function toIsoDate(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

export function todayIso(now: Date = new Date()): string {
  return toIsoDate(now);
}

export function currentMonth(now: Date = new Date()): MonthRef {
  return { year: now.getFullYear(), month: now.getMonth() + 1 };
}

export function addMonths(ref: MonthRef, delta: number): MonthRef {
  const index = ref.year * 12 + (ref.month - 1) + delta;
  return { year: Math.floor(index / 12), month: (index % 12) + 1 };
}

export function monthKey(ref: MonthRef): string {
  return `${ref.year}-${String(ref.month).padStart(2, '0')}`;
}

export function parseMonthKey(key: string): MonthRef {
  const [year, month] = key.split('-').map(Number);
  return { year, month };
}

/** Inclusive first and last day of the month as ISO dates. */
export function monthBounds(ref: MonthRef): { from: string; to: string } {
  const lastDay = new Date(ref.year, ref.month, 0).getDate();
  const prefix = monthKey(ref);
  return { from: `${prefix}-01`, to: `${prefix}-${String(lastDay).padStart(2, '0')}` };
}

const monthFormat = new Intl.DateTimeFormat('en-GB', { month: 'long', year: 'numeric' });
const shortMonthFormat = new Intl.DateTimeFormat('en-GB', { month: 'short' });
const dayFormat = new Intl.DateTimeFormat('en-GB', {
  weekday: 'short',
  day: 'numeric',
  month: 'short',
});
const dayWithYearFormat = new Intl.DateTimeFormat('en-GB', {
  day: 'numeric',
  month: 'short',
  year: 'numeric',
});

export function formatMonth(ref: MonthRef): string {
  return monthFormat.format(new Date(ref.year, ref.month - 1, 1));
}

export function formatShortMonth(key: string): string {
  const ref = parseMonthKey(key);
  return shortMonthFormat.format(new Date(ref.year, ref.month - 1, 1));
}

function fromIso(iso: string): Date {
  const [year, month, day] = iso.split('-').map(Number);
  return new Date(year, month - 1, day);
}

/** "Today", "Yesterday", "Thu 25 Sep" or "25 Sep 2025" for older years. */
export function formatDayLabel(iso: string, now: Date = new Date()): string {
  const today = todayIso(now);

  if (iso === today) {
    return 'Today';
  }

  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);

  if (iso === toIsoDate(yesterday)) {
    return 'Yesterday';
  }

  const date = fromIso(iso);

  return date.getFullYear() === now.getFullYear()
    ? dayFormat.format(date)
    : dayWithYearFormat.format(date);
}

export function formatDate(iso: string): string {
  return dayWithYearFormat.format(fromIso(iso));
}
