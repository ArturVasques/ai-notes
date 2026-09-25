import { httpResource } from '@angular/common/http';
import { Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { environment } from '../../../environments/environment';
import { UserProfile } from '../../core/api/api.models';
import { AuthService } from '../../core/auth/auth.service';
import { ThemeMode, ThemeService } from '../../core/theme.service';
import { IconComponent } from '../../shared/icon.component';

@Component({
  selector: 'app-settings-page',
  imports: [RouterLink, IconComponent],
  template: `
    <div class="page">
      <div class="page-head">
        <div class="page-head__titles">
          <span class="eyebrow">Account</span>
          <h1>Settings</h1>
        </div>
      </div>

      <div class="group">
        <div class="row-item row-item--static">
          <span class="row-item__icon"
            ><app-icon name="user" [size]="17" [strokeWidth]="1.75"
          /></span>
          <span class="row-item__main">
            <span class="row-item__title">{{ profile.value()?.name ?? auth.displayName() }}</span>
            <span class="row-item__sub truncate">
              {{ profile.value()?.email ?? auth.account()?.username ?? '' }}
            </span>
          </span>
        </div>
      </div>

      <div class="stack" style="gap: var(--s-2)">
        <span class="eyebrow">Manage</span>
        <nav class="group" aria-label="Manage">
          <a class="row-item" routerLink="/settings/accounts">
            <span class="row-item__icon"
              ><app-icon name="wallet" [size]="17" [strokeWidth]="1.75"
            /></span>
            <span class="row-item__main"><span class="row-item__title">Accounts</span></span>
            <app-icon class="row-item__chevron" name="chevron-right" [size]="16" />
          </a>
          <a class="row-item" routerLink="/settings/categories">
            <span class="row-item__icon"
              ><app-icon name="tag" [size]="17" [strokeWidth]="1.75"
            /></span>
            <span class="row-item__main"><span class="row-item__title">Categories</span></span>
            <app-icon class="row-item__chevron" name="chevron-right" [size]="16" />
          </a>
          <a class="row-item" routerLink="/settings/investment-assets">
            <span class="row-item__icon"
              ><app-icon name="chart-candlestick" [size]="17" [strokeWidth]="1.75"
            /></span>
            <span class="row-item__main"
              ><span class="row-item__title">Investment assets</span></span
            >
            <app-icon class="row-item__chevron" name="chevron-right" [size]="16" />
          </a>
        </nav>
      </div>

      <div class="stack" style="gap: var(--s-2)">
        <span class="eyebrow">Appearance</span>
        <div class="segmented" role="radiogroup" aria-label="Appearance">
          @for (option of themeOptions; track option.mode) {
            <button
              type="button"
              role="radio"
              class="segmented__option"
              [class.segmented__option--active]="theme.mode() === option.mode"
              [attr.aria-checked]="theme.mode() === option.mode"
              (click)="theme.setMode(option.mode)"
            >
              {{ option.label }}
            </button>
          }
        </div>
        <p class="group__footer" style="padding: 0">
          Night uses a pure black background for the iPhone display.
        </p>
      </div>

      <div class="group">
        <button type="button" class="row-item" (click)="auth.logout()">
          <span class="row-item__main"><span class="row-item__title neg">Sign out</span></span>
        </button>
      </div>

      <p class="small faint">
        Amounts are stored to the cent; every figure is computed by the API.
      </p>
    </div>
  `,
})
export class SettingsPage {
  readonly auth = inject(AuthService);
  readonly theme = inject(ThemeService);
  readonly themeOptions: { mode: ThemeMode; label: string }[] = [
    { mode: 'system', label: 'System' },
    { mode: 'light', label: 'Day' },
    { mode: 'dark', label: 'Night' },
  ];
  readonly profile = httpResource<UserProfile>(() => `${environment.apiBaseUrl}/me`);
}
