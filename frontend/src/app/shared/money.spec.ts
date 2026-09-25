import { formatMinor, formatRate, minorToInput, parseAmountToMinor, splitMinor } from './money';

describe('parseAmountToMinor', () => {
  it.each([
    ['24,80', 2480],
    ['24.80', 2480],
    ['24', 2400],
    ['24,8', 2480],
    ['0,05', 5],
    ['1.234,56', 123456],
    ['1,234.56', 123456],
    [' 3 050,00 € ', 305000],
  ])('parses %s as %i minor units', (input, expected) => {
    expect(parseAmountToMinor(input)).toBe(expected);
  });

  it.each(['', 'abc', '-5', '0', '0,00', '24,805', '1e3', '24.', ',80'])('rejects %s', (input) => {
    expect(parseAmountToMinor(input)).toBeNull();
  });

  it('never goes through floating point', () => {
    expect(parseAmountToMinor('0,29')).toBe(29);
    expect(parseAmountToMinor('1,15')).toBe(115);
  });
});

describe('formatMinor', () => {
  it('formats cents with two decimals and the euro sign', () => {
    expect(formatMinor(2480)).toBe('€24.80');
    expect(formatMinor(305000)).toBe('€3,050.00');
    expect(formatMinor(5)).toBe('€0.05');
    expect(formatMinor(0)).toBe('€0.00');
  });

  it('shows signs when asked', () => {
    expect(formatMinor(-2480)).toBe('-€24.80');
    expect(formatMinor(2480, { signed: true })).toBe('+€24.80');
    expect(formatMinor(-2480, { signed: true })).toBe('-€24.80');
    expect(splitMinor(305000)).toEqual({ sign: '', units: '3,050', cents: '00' });
  });
});

describe('minorToInput', () => {
  it('produces an editable amount', () => {
    expect(minorToInput(2480)).toBe('24.80');
    expect(minorToInput(5)).toBe('0.05');
    expect(minorToInput(-1250)).toBe('12.50');
  });
});

describe('formatRate', () => {
  it('formats ratios as percentages', () => {
    expect(formatRate(0.3333)).toBe('33.3%');
    expect(formatRate(null)).toBe('—');
  });
});
