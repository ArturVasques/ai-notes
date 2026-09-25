import { Injectable, signal } from '@angular/core';

/**
 * Invalidation signal for API-backed resources. Every `httpResource` that
 * reads `version()` in its request function refetches after a mutation
 * calls `bump()`, so a saved transaction updates the dashboard, the
 * history and the balances without wiring events between features.
 */
@Injectable({ providedIn: 'root' })
export class RefreshService {
  private readonly counter = signal(0);

  readonly version = this.counter.asReadonly();

  bump(): void {
    this.counter.update((value) => value + 1);
  }
}
