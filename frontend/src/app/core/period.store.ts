import { computed, Injectable, signal } from '@angular/core';
import {
  addMonths,
  currentMonth,
  formatMonth,
  monthBounds,
  monthKey,
  MonthRef,
} from '../shared/dates';

/** The month currently shown by Home, Transactions and Insights. */
@Injectable({ providedIn: 'root' })
export class PeriodStore {
  private readonly selected = signal<MonthRef>(currentMonth());

  readonly month = this.selected.asReadonly();
  readonly key = computed(() => monthKey(this.selected()));
  readonly bounds = computed(() => monthBounds(this.selected()));
  readonly label = computed(() => formatMonth(this.selected()));
  readonly isCurrent = computed(() => this.key() === monthKey(currentMonth()));

  previous(): void {
    this.selected.update((month) => addMonths(month, -1));
  }

  next(): void {
    this.selected.update((month) => addMonths(month, 1));
  }

  reset(): void {
    this.selected.set(currentMonth());
  }
}
