import {
  afterNextRender,
  Component,
  computed,
  DestroyRef,
  ElementRef,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router } from '@angular/router';
import { filter, map } from 'rxjs';
import { DashboardPage } from '../../features/dashboard/dashboard.page';
import { InsightsPage } from '../../features/insights/insights.page';
import { SettingsPage } from '../../features/settings/settings.page';
import { TransactionsPage } from '../../features/transactions/transactions.page';
import { commitSwipe, rubberBand, TAB_ROUTES, tabIndexOf } from './swipe-navigation';

const ENGAGE_PX = 10;
const HORIZONTAL_RATIO = 1.25;
const MAX_TILT_DEG = 12;

/**
 * The four top-level tabs side by side, like a native view pager. Each tab
 * keeps its own scroll position. A horizontal drag moves the pages under
 * the finger with a slight depth effect; releasing settles on the nearest
 * tab (or flicks to the next one) and the router URL follows. Tapping the
 * navigation animates the pager the same way.
 */
@Component({
  selector: 'app-tab-pager',
  imports: [DashboardPage, TransactionsPage, InsightsPage, SettingsPage],
  template: `
    <div class="pager" #pager>
      <div
        class="pager__track"
        [class.pager__track--animate]="!dragging()"
        [style.transform]="trackTransform()"
        (transitionend)="onTrackTransitionEnd($event)"
      >
        @for (index of indexes; track index) {
          <section
            class="pager__pane"
            [class.pager__pane--hidden]="isHidden(index)"
            [style.transform]="paneTransform(index)"
            [style.opacity]="paneOpacity(index)"
            [inert]="index !== currentIndex()"
          >
            <div class="shell__content">
              @switch (index) {
                @case (0) {
                  <app-dashboard-page />
                }
                @case (1) {
                  <app-transactions-page />
                }
                @case (2) {
                  <app-insights-page />
                }
                @case (3) {
                  <app-settings-page />
                }
              }
            </div>
          </section>
        }
      </div>
    </div>
  `,
})
export class TabPagerComponent {
  private readonly router = inject(Router);
  private readonly pager = viewChild.required<ElementRef<HTMLElement>>('pager');

  readonly indexes = [0, 1, 2, 3];

  /** Tab selected by the URL (the last tab stays current on nested pages). */
  private readonly routedIndex = toSignal(
    this.router.events.pipe(
      filter((event): event is NavigationEnd => event instanceof NavigationEnd),
      map((event) => tabIndexOf(event.urlAfterRedirects)),
      filter((index) => index !== -1),
    ),
    { initialValue: Math.max(0, tabIndexOf(this.router.url)) },
  );

  /** Optimistic target while the router catches up after a committed swipe. */
  private readonly pending = signal<number | null>(null);

  readonly currentIndex = computed(() => this.pending() ?? this.routedIndex());

  readonly dragging = signal(false);
  private readonly settling = signal(false);
  private readonly dragPx = signal(0);
  private readonly widthPx = signal(1);

  /** Fractional position of the viewport over the track (0 = first tab). */
  private readonly position = computed(() => this.currentIndex() - this.dragPx() / this.widthPx());

  readonly trackTransform = computed(() => `translate3d(${-this.position() * 100}%, 0, 0)`);

  private gesture: {
    startX: number;
    startY: number;
    lastX: number;
    lastTime: number;
    velocity: number;
    engaged: boolean;
    ignored: boolean;
  } | null = null;

  constructor() {
    const destroyRef = inject(DestroyRef);

    afterNextRender(() => {
      const element = this.pager().nativeElement;
      const onStart = (event: TouchEvent) => this.onTouchStart(event);
      const onMove = (event: TouchEvent) => this.onTouchMove(event);
      const onEnd = () => this.onTouchEnd();

      element.addEventListener('touchstart', onStart, { passive: true });
      // Not passive: once a horizontal drag is engaged, vertical scrolling is
      // suppressed so the page follows the finger cleanly.
      element.addEventListener('touchmove', onMove, { passive: false });
      element.addEventListener('touchend', onEnd, { passive: true });
      element.addEventListener('touchcancel', onEnd, { passive: true });

      destroyRef.onDestroy(() => {
        element.removeEventListener('touchstart', onStart);
        element.removeEventListener('touchmove', onMove);
        element.removeEventListener('touchend', onEnd);
        element.removeEventListener('touchcancel', onEnd);
      });
    });
  }

  /** Offset of a pane from the viewport, clamped to one screen. */
  private offset(index: number): number {
    return Math.max(-1, Math.min(1, index - this.position()));
  }

  isHidden(index: number): boolean {
    if (this.dragging() || this.settling()) {
      return Math.abs(index - this.position()) >= 1.001;
    }

    return index !== this.currentIndex();
  }

  paneTransform(index: number): string {
    const offset = this.offset(index);
    const tilt = -offset * MAX_TILT_DEG;
    const scale = 1 - Math.abs(offset) * 0.06;

    return `perspective(1400px) rotateY(${tilt.toFixed(2)}deg) scale(${scale.toFixed(3)})`;
  }

  paneOpacity(index: number): number {
    return 1 - Math.abs(this.offset(index)) * 0.35;
  }

  private onTouchStart(event: TouchEvent): void {
    if (event.touches.length !== 1) {
      this.gesture = null;
      return;
    }

    const target = event.target as Element | null;
    const touch = event.touches[0];

    this.gesture = {
      startX: touch.clientX,
      startY: touch.clientY,
      lastX: touch.clientX,
      lastTime: performance.now(),
      velocity: 0,
      engaged: false,
      ignored: !!target?.closest('dialog, input, select, textarea, [data-no-swipe]'),
    };
    this.widthPx.set(Math.max(1, this.pager().nativeElement.clientWidth));
  }

  private onTouchMove(event: TouchEvent): void {
    const gesture = this.gesture;

    if (!gesture || gesture.ignored || event.touches.length !== 1) {
      return;
    }

    const touch = event.touches[0];
    const dx = touch.clientX - gesture.startX;
    const dy = touch.clientY - gesture.startY;

    if (!gesture.engaged) {
      if (Math.abs(dx) < ENGAGE_PX) {
        return;
      }

      if (Math.abs(dx) < Math.abs(dy) * HORIZONTAL_RATIO) {
        // Vertical intent: let the pane scroll and ignore the rest of it.
        gesture.ignored = true;
        return;
      }

      gesture.engaged = true;
      this.settling.set(false);
      this.dragging.set(true);
    }

    event.preventDefault();

    const now = performance.now();
    const elapsed = Math.max(1, now - gesture.lastTime);
    gesture.velocity = (touch.clientX - gesture.lastX) / elapsed;
    gesture.lastX = touch.clientX;
    gesture.lastTime = now;

    const index = this.currentIndex();
    const atEdge = (dx > 0 && index === 0) || (dx < 0 && index === TAB_ROUTES.length - 1);

    this.dragPx.set(
      atEdge ? rubberBand(dx) : Math.max(-this.widthPx(), Math.min(this.widthPx(), dx)),
    );
  }

  private onTouchEnd(): void {
    const gesture = this.gesture;
    this.gesture = null;

    if (!gesture?.engaged) {
      return;
    }

    const delta = commitSwipe({
      dragPx: this.dragPx(),
      widthPx: this.widthPx(),
      velocityPxPerMs: gesture.velocity,
    });
    const target = this.currentIndex() + delta;

    this.settling.set(true);
    this.dragging.set(false);
    this.dragPx.set(0);

    if (delta !== 0 && target >= 0 && target < TAB_ROUTES.length) {
      this.pending.set(target);
      void this.router.navigateByUrl(TAB_ROUTES[target], { info: { swipe: true } }).finally(() => {
        this.pending.set(null);
      });
    }
  }

  onTrackTransitionEnd(event: TransitionEvent): void {
    if (event.target === event.currentTarget && event.propertyName === 'transform') {
      this.settling.set(false);
    }
  }
}
