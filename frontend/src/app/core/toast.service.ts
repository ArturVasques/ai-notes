import { Injectable, signal } from '@angular/core';

export interface Toast {
  id: number;
  message: string;
  tone: 'neutral' | 'success' | 'error';
  leaving: boolean;
}

/** Short, non-blocking confirmations ("Expense added"). One at a time. */
@Injectable({ providedIn: 'root' })
export class ToastService {
  private readonly state = signal<Toast | null>(null);
  private counter = 0;
  private hideTimer: ReturnType<typeof setTimeout> | null = null;
  private removeTimer: ReturnType<typeof setTimeout> | null = null;

  readonly current = this.state.asReadonly();

  show(message: string, tone: Toast['tone'] = 'success'): void {
    this.clearTimers();
    this.state.set({ id: ++this.counter, message, tone, leaving: false });

    this.hideTimer = setTimeout(() => {
      this.state.update((toast) => (toast ? { ...toast, leaving: true } : toast));
      this.removeTimer = setTimeout(() => this.state.set(null), 260);
    }, 2200);
  }

  private clearTimers(): void {
    if (this.hideTimer) clearTimeout(this.hideTimer);
    if (this.removeTimer) clearTimeout(this.removeTimer);
    this.hideTimer = null;
    this.removeTimer = null;
  }
}
