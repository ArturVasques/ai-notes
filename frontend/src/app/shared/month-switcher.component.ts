import { Component, inject, input } from '@angular/core';
import { PeriodStore } from '../core/period.store';
import { IconComponent } from './icon.component';

/** Page title that is also the period control: "September 2026 ‹ ›". */
@Component({
  selector: 'app-month-switcher',
  imports: [IconComponent],
  template: `
    <div class="page-head">
      <div class="page-head__titles">
        @if (eyebrow()) {
          <span class="eyebrow">{{ eyebrow() }}</span>
        }
        <div class="month">
          <button
            type="button"
            class="month__label"
            [title]="period.isCurrent() ? '' : 'Back to this month'"
            (click)="period.reset()"
          >
            {{ period.label() }}
          </button>
        </div>
      </div>
      <div class="page-head__tools">
        <ng-content />
        <div class="month__nav glass-control">
          <button
            type="button"
            class="icon-button"
            aria-label="Previous month"
            (click)="period.previous()"
          >
            <app-icon name="chevron-left" [size]="20" />
          </button>
          <button type="button" class="icon-button" aria-label="Next month" (click)="period.next()">
            <app-icon name="chevron-right" [size]="20" />
          </button>
        </div>
      </div>
    </div>
  `,
})
export class MonthSwitcherComponent {
  readonly period = inject(PeriodStore);
  readonly eyebrow = input('');
}
