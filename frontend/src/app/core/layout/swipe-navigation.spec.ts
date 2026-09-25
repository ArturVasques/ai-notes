import { commitSwipe, isTabUrl, rubberBand, tabIndexOf } from './swipe-navigation';

describe('tabIndexOf', () => {
  it('maps the top-level tabs in order Home → Activity → Insights → Settings', () => {
    expect(tabIndexOf('/')).toBe(0);
    expect(tabIndexOf('/transactions')).toBe(1);
    expect(tabIndexOf('/insights?x=1')).toBe(2);
    expect(tabIndexOf('/settings')).toBe(3);
  });

  it('treats nested pages as outside the pager', () => {
    expect(tabIndexOf('/settings/accounts')).toBe(-1);
    expect(isTabUrl('/settings/categories')).toBe(false);
    expect(isTabUrl('/insights')).toBe(true);
  });
});

describe('commitSwipe', () => {
  it('moves to the next tab after a long enough drag to the left', () => {
    expect(commitSwipe({ dragPx: -140, widthPx: 400, velocityPxPerMs: 0 })).toBe(1);
  });

  it('moves to the previous tab on a quick flick to the right', () => {
    expect(commitSwipe({ dragPx: -20, widthPx: 400, velocityPxPerMs: 0.9 })).toBe(-1);
  });

  it('springs back after a short, slow drag', () => {
    expect(commitSwipe({ dragPx: 60, widthPx: 400, velocityPxPerMs: 0.1 })).toBe(0);
  });
});

describe('rubberBand', () => {
  it('resists movement past the edges', () => {
    expect(Math.abs(rubberBand(100))).toBeLessThan(40);
  });
});
