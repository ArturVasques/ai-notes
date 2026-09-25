/**
 * Pure helpers for the swipeable tab pager.
 */

export const TAB_ROUTES = ['/', '/transactions', '/insights', '/settings'] as const;

/** Index of the top-level tab a URL belongs to, or -1 for nested pages. */
export function tabIndexOf(url: string): number {
  const path = url.split('?')[0].split('#')[0];
  return TAB_ROUTES.indexOf(path as (typeof TAB_ROUTES)[number]);
}

export function isTabUrl(url: string): boolean {
  return tabIndexOf(url) !== -1;
}

export interface SwipeRelease {
  /** Finger displacement in pixels since the gesture started (left < 0). */
  dragPx: number;
  widthPx: number;
  /** Pixels per millisecond at release (left < 0). */
  velocityPxPerMs: number;
}

const COMMIT_FRACTION = 0.28;
const FLICK_VELOCITY = 0.45;

/**
 * Which tab the pager should settle on when the finger lifts: +1 for the
 * next tab, -1 for the previous one, 0 to spring back.
 */
export function commitSwipe(release: SwipeRelease): -1 | 0 | 1 {
  const { dragPx, widthPx, velocityPxPerMs } = release;
  const fraction = widthPx > 0 ? dragPx / widthPx : 0;
  const flick = Math.abs(velocityPxPerMs) >= FLICK_VELOCITY;

  if (Math.abs(fraction) >= COMMIT_FRACTION || flick) {
    const direction = flick ? velocityPxPerMs : dragPx;
    return direction < 0 ? 1 : -1;
  }

  return 0;
}

/** Resistance when dragging past the first or last tab. */
export function rubberBand(dragPx: number): number {
  return dragPx * 0.28;
}
