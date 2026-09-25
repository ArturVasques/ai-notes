import { Component, inject, signal } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { QuickAddSheetComponent } from '../../features/transactions/quick-add-sheet.component';
import { IconComponent } from '../../shared/icon.component';
import { ThemeService } from '../theme.service';
import { ToastService } from '../toast.service';
import { TabPagerComponent } from './tab-pager.component';

/**
 * Authenticated layout: the swipeable tab pager, nested pages (Settings
 * sub-pages) on top of it, floating glass navigation (bottom pill on phones,
 * side rail on desktop), the Quick Add sheet and toasts.
 */
@Component({
  selector: 'app-shell',
  imports: [
    RouterOutlet,
    RouterLink,
    RouterLinkActive,
    IconComponent,
    QuickAddSheetComponent,
    TabPagerComponent,
  ],
  template: `
    <div class="shell">
      <app-tab-pager />

      <div class="subpage" [class.subpage--open]="subpageOpen()" [inert]="!subpageOpen()">
        <div class="shell__content">
          <router-outlet (activate)="subpageOpen.set(true)" (deactivate)="subpageOpen.set(false)" />
        </div>
      </div>

      <div class="top-blur" aria-hidden="true"></div>

      <nav class="nav glass" aria-label="Main">
        <a
          class="nav__item"
          routerLink="/"
          routerLinkActive="nav__item--active"
          [routerLinkActiveOptions]="{ exact: true }"
        >
          <app-icon name="house" [size]="22" [strokeWidth]="1.75" />
          <span>Home</span>
        </a>
        <a class="nav__item" routerLink="/transactions" routerLinkActive="nav__item--active">
          <app-icon name="list" [size]="22" [strokeWidth]="1.75" />
          <span>Activity</span>
        </a>
        <button
          type="button"
          class="nav__add"
          aria-label="Add transaction"
          (click)="quickAddOpen.set(true)"
        >
          <app-icon name="plus" [size]="22" [strokeWidth]="2.25" />
          <span class="nav__add-label">New</span>
        </button>
        <a class="nav__item" routerLink="/insights" routerLinkActive="nav__item--active">
          <app-icon name="chart-pie" [size]="22" [strokeWidth]="1.75" />
          <span>Insights</span>
        </a>
        <a class="nav__item" routerLink="/settings" routerLinkActive="nav__item--active">
          <app-icon name="settings" [size]="22" [strokeWidth]="1.75" />
          <span>Settings</span>
        </a>
      </nav>

      <app-quick-add-sheet [(open)]="quickAddOpen" />

      @if (toasts.current(); as toast) {
        <div
          class="toast glass"
          [class.toast--leaving]="toast.leaving"
          role="status"
          aria-live="polite"
        >
          @if (toast.tone === 'success') {
            <app-icon name="check" [size]="16" />
          } @else if (toast.tone === 'error') {
            <app-icon name="triangle-alert" [size]="16" />
          }
          <span>{{ toast.message }}</span>
        </div>
      }
    </div>
  `,
})
export class ShellComponent {
  readonly toasts = inject(ToastService);
  // Instantiated here so the appearance applies as soon as the shell renders.
  private readonly theme = inject(ThemeService);

  readonly quickAddOpen = signal(false);
  readonly subpageOpen = signal(false);
}
