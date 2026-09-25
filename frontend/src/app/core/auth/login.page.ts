import { Component, inject } from '@angular/core';
import { IconComponent } from '../../shared/icon.component';
import { AuthService } from './auth.service';

@Component({
  selector: 'app-login-page',
  imports: [IconComponent],
  template: `
    <main class="login">
      <section class="login__inner fade-in">
        <div class="login__mark">
          <app-icon name="wallet" [size]="22" />
        </div>
        <div class="stack" style="gap: 6px">
          <h1 class="login__title">Personal Finance</h1>
          <p class="muted">Income, expenses, savings and investments — to the cent.</p>
        </div>
        <button type="button" class="btn btn--primary btn--block" (click)="login()">
          Sign in with Microsoft
        </button>
      </section>
    </main>
  `,
})
export class LoginPage {
  private readonly auth = inject(AuthService);

  login(): void {
    this.auth.login();
  }
}
