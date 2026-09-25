/**
 * Money helpers. Amounts are integers in minor units (cents) everywhere in
 * the application, exactly as in the API; only these two functions convert
 * to and from what a person types or reads.
 */

export const MAX_AMOUNT_MINOR = 999_999_999_999;

/**
 * Parse a typed amount such as "24,80", "24.80", "1.234,56" or "24" into
 * minor units. Returns null for anything that is not a positive amount with
 * at most two decimals. Never goes through floating point.
 */
export function parseAmountToMinor(input: string): number | null {
  let text = input.replace(/\s|€/g, '');

  if (text === '') {
    return null;
  }

  const lastComma = text.lastIndexOf(',');
  const lastDot = text.lastIndexOf('.');

  if (lastComma >= 0 && lastDot >= 0) {
    // Both present: the last one is the decimal separator, the other groups
    // thousands ("1.234,56" or "1,234.56").
    const decimal = lastComma > lastDot ? ',' : '.';
    const grouping = decimal === ',' ? '.' : ',';
    text = text.split(grouping).join('').replace(decimal, '.');
  } else {
    text = text.replace(',', '.');
  }

  const match = /^(\d+)(?:\.(\d{1,2}))?$/.exec(text);

  if (!match) {
    return null;
  }

  const units = match[1];
  const cents = (match[2] ?? '').padEnd(2, '0');
  const minor = Number(`${units}${cents}`);

  if (!Number.isSafeInteger(minor) || minor <= 0 || minor > MAX_AMOUNT_MINOR) {
    return null;
  }

  return minor;
}

/** Text for an input field when editing an existing amount: 2480 → "24.80". */
export function minorToInput(minor: number): string {
  const abs = Math.abs(minor);
  return `${Math.floor(abs / 100)}.${String(abs % 100).padStart(2, '0')}`;
}

// Groups the integer part only ("3,050"); the cents are appended by hand so
// the output never depends on floating point rounding.
const grouped = new Intl.NumberFormat('en-GB', { maximumFractionDigits: 0 });

export interface MoneyParts {
  sign: '' | '-' | '+';
  units: string;
  cents: string;
}

/** 248000 → { sign: '', units: '2,480', cents: '00' } for large displays. */
export function splitMinor(minor: number, options: { signed?: boolean } = {}): MoneyParts {
  const abs = Math.abs(minor);
  const sign = minor < 0 ? '-' : options.signed && minor > 0 ? '+' : '';

  return {
    sign,
    units: grouped.format(Math.floor(abs / 100)),
    cents: String(abs % 100).padStart(2, '0'),
  };
}

/**
 * Display an amount: 248000 → "€2,480.00". With `signed`, a plus or minus
 * sign is always shown ("+€3,050.00", "-€24.80").
 */
export function formatMinor(minor: number, options: { signed?: boolean } = {}): string {
  const { sign, units, cents } = splitMinor(minor, options);
  return `${sign}€${units}.${cents}`;
}

/** 0.3333 → "33.3%". */
export function formatRate(rate: number | null | undefined): string {
  if (rate === null || rate === undefined) {
    return '—';
  }

  return `${(rate * 100).toFixed(1)}%`;
}
