import { Component, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Transaction } from '../../core/api/api.models';
import { PeriodStore } from '../../core/period.store';
import { IconComponent } from '../../shared/icon.component';
import { formatRate, splitMinor } from '../../shared/money';
import { MoneyPipe } from '../../shared/money.pipe';
import { MonthSwitcherComponent } from '../../shared/month-switcher.component';
import { AccountsService } from '../accounts/accounts.service';
import { ReportsService } from '../insights/reports.service';
import { QuickAddSheetComponent } from '../transactions/quick-add-sheet.component';
import { TransactionItemComponent } from '../transactions/transaction-item.component';
import { TransactionsService } from '../transactions/transactions.service';

@Component({
  selector: 'app-dashboard-page',
  imports: [
    RouterLink,
    IconComponent,
    MoneyPipe,
    MonthSwitcherComponent,
    TransactionItemComponent,
    QuickAddSheetComponent,
  ],
  template: `
    <div class="page">
      <app-month-switcher eyebrow="Overview" />

      @if (accounts.all.hasValue() && accounts.active().length === 0) {
        <section class="stack">
          <h2>Welcome</h2>
          <p class="muted">
            Start by creating the accounts where your money lives, then add your first transaction
            with the + button.
          </p>
          <a class="btn btn--primary" routerLink="/settings/accounts">Create an account</a>
        </section>
      }

      @for (key of [period.key()]; track key) {
        <div class="stack fade-in" style="gap: var(--s-8)">
          @if (overview.value(); as o) {
            <section class="stack" style="gap: var(--s-5)">
              <div class="hero">
                <span class="hero__label">Income</span>
                <div class="hero__value">
                  €{{ parts(o.income_minor).units
                  }}<span class="hero__cents">.{{ parts(o.income_minor).cents }}</span>
                </div>
              </div>

              <div class="metrics">
                <div class="metric">
                  <span class="metric__value">{{ o.effective_expenses_minor | money }}</span>
                  <span class="metric__label">Spent</span>
                  <span class="metric__hint">{{
                    share(o.effective_expenses_minor, o.income_minor)
                  }}</span>
                </div>
                <div class="metric">
                  <span
                    class="metric__value"
                    [class.pos]="o.net_savings_minor > 0"
                    [class.neg]="o.net_savings_minor < 0"
                  >
                    {{ o.net_savings_minor | money }}
                  </span>
                  <span class="metric__label">Saved</span>
                  <span class="metric__hint">{{ rate(o.savings_rate) }} rate</span>
                </div>
                <div class="metric">
                  <span class="metric__value inv">{{
                    o.allocation.investments_minor | money
                  }}</span>
                  <span class="metric__label">Invested</span>
                  <span class="metric__hint">{{
                    share(o.allocation.investments_minor, o.income_minor)
                  }}</span>
                </div>
              </div>

              <p class="small faint tnum">
                Net cash flow {{ o.net_cash_flow_minor | money: 'signed' }}
                @if (o.reimbursements_attributed_minor > 0) {
                  · {{ o.reimbursements_attributed_minor | money }} refunded
                }
                @if (o.transfers_minor > 0) {
                  · {{ o.transfers_minor | money }} moved between accounts
                }
              </p>
            </section>
          } @else if (overview.error()) {
            <p class="form-error">Could not load this month.</p>
          } @else {
            <section class="stack" style="gap: var(--s-5)" aria-hidden="true">
              <span class="skeleton" style="width: 60px; height: 14px"></span>
              <span class="skeleton" style="width: 200px; height: 44px"></span>
              <div class="metrics">
                <span class="skeleton" style="height: 38px"></span>
                <span class="skeleton" style="height: 38px"></span>
                <span class="skeleton" style="height: 38px"></span>
              </div>
            </section>
          }

          @if (spending.value(); as breakdown) {
            @if (breakdown.items.length > 0) {
              <section class="section">
                <div class="section__head">
                  <h2>Spending</h2>
                  <a class="section__link" routerLink="/insights">Insights</a>
                </div>
                <div class="rows">
                  @for (item of breakdown.items.slice(0, 5); track item.category_id) {
                    <div class="breakdown">
                      <div class="breakdown__line">
                        <span class="breakdown__name">
                          <app-icon [name]="item.icon" [size]="16" [strokeWidth]="1.75" />
                          <span class="truncate">{{ item.name }}</span>
                        </span>
                        <span class="tnum">{{ item.effective_minor | money }}</span>
                      </div>
                      <div class="bar">
                        <div
                          class="bar__fill"
                          [style.width.%]="
                            percent(item.effective_minor, breakdown.items[0].effective_minor)
                          "
                        ></div>
                      </div>
                    </div>
                  }
                </div>
              </section>
            }
          }

          <section class="section">
            <div class="section__head">
              <h2>Recent</h2>
              <a class="section__link" routerLink="/transactions">See all</a>
            </div>
            @if (recent.value(); as page) {
              @if (page.items.length > 0) {
                <div class="rows">
                  @for (transaction of page.items; track transaction.id) {
                    <app-transaction-item [transaction]="transaction" (selected)="edit($event)" />
                  }
                </div>
              } @else {
                <div class="empty">
                  <p class="empty__title">Nothing this month yet</p>
                  <p>Use + to add an expense, income, transfer or investment.</p>
                </div>
              }
            } @else {
              <div class="rows" aria-hidden="true">
                <span class="skeleton" style="height: 54px; margin: 6px 0"></span>
                <span class="skeleton" style="height: 54px; margin: 6px 0"></span>
                <span class="skeleton" style="height: 54px; margin: 6px 0"></span>
              </div>
            }
          </section>
        </div>
      }

      <app-quick-add-sheet [(open)]="editOpen" [transaction]="editing()" />
    </div>
  `,
})
export class DashboardPage {
  readonly accounts = inject(AccountsService);
  readonly period = inject(PeriodStore);
  private readonly reports = inject(ReportsService);
  private readonly transactions = inject(TransactionsService);

  readonly overview = this.reports.overview(() => this.period.bounds());
  readonly spending = this.reports.categories(() => this.period.bounds(), 'EXPENSE');
  readonly recent = this.transactions.page(
    () => ({ from: this.period.bounds().from, to: this.period.bounds().to }),
    () => 5,
  );

  readonly editing = signal<Transaction | null>(null);
  readonly editOpen = signal(false);

  parts(minor: number) {
    return splitMinor(minor);
  }

  rate(value: number | null): string {
    return formatRate(value);
  }

  /** "41.7% of income", or nothing without income. */
  share(part: number, income: number): string {
    return income > 0 ? `${((part / income) * 100).toFixed(1)}% of income` : '';
  }

  percent(part: number, whole: number): number {
    if (whole <= 0) {
      return 0;
    }

    return Math.max(0, Math.min(100, (part / whole) * 100));
  }

  edit(transaction: Transaction): void {
    this.editing.set(transaction);
    this.editOpen.set(true);
  }
}
