import { Component, computed, inject } from '@angular/core';
import { PeriodStore } from '../../core/period.store';
import { formatShortMonth } from '../../shared/dates';
import { IconComponent } from '../../shared/icon.component';
import { formatRate } from '../../shared/money';
import { MoneyPipe } from '../../shared/money.pipe';
import { MonthSwitcherComponent } from '../../shared/month-switcher.component';
import { ReportsService } from './reports.service';

@Component({
  selector: 'app-insights-page',
  imports: [IconComponent, MoneyPipe, MonthSwitcherComponent],
  template: `
    <div class="page">
      <app-month-switcher eyebrow="Insights" />

      @for (key of [period.key()]; track key) {
        <div class="stack fade-in" style="gap: var(--s-8)">
          @if (savings.value(); as s) {
            <section class="stack" style="gap: var(--s-5)">
              <div class="metrics" style="border-top: 0; padding-top: 0">
                <div class="metric">
                  <span class="metric__value pos">{{ s.income_minor | money }}</span>
                  <span class="metric__label">Income</span>
                </div>
                <div class="metric">
                  <span class="metric__value">{{ s.effective_expenses_minor | money }}</span>
                  <span class="metric__label">Spent</span>
                </div>
                <div class="metric">
                  <span
                    class="metric__value"
                    [class.pos]="s.net_savings_minor > 0"
                    [class.neg]="s.net_savings_minor < 0"
                  >
                    {{ s.net_savings_minor | money }}
                  </span>
                  <span class="metric__label">Saved · {{ rate(s.savings_rate) }}</span>
                </div>
              </div>
            </section>

            <section class="section">
              <div class="section__head"><h2>Where the savings went</h2></div>
              @if (s.net_savings_minor > 0) {
                <div class="allocation">
                  <div
                    class="allocation__segment dot--savings"
                    [style.width.%]="
                      percent(s.allocation.savings_accounts_minor, s.net_savings_minor)
                    "
                  ></div>
                  <div
                    class="allocation__segment dot--invest"
                    [style.width.%]="percent(s.allocation.investments_minor, s.net_savings_minor)"
                  ></div>
                  <div
                    class="allocation__segment dot--retained"
                    [style.width.%]="percent(s.allocation.retained_cash_minor, s.net_savings_minor)"
                  ></div>
                </div>
              }
              <div class="rows">
                <div class="row-item row-item--static">
                  <span class="dot dot--savings"></span>
                  <span class="row-item__main"
                    ><span class="row-item__title">Savings accounts</span></span
                  >
                  <span class="row-item__value">{{
                    s.allocation.savings_accounts_minor | money
                  }}</span>
                </div>
                <div class="row-item row-item--static">
                  <span class="dot dot--invest"></span>
                  <span class="row-item__main"
                    ><span class="row-item__title">Investments</span></span
                  >
                  <span class="row-item__value">{{ s.allocation.investments_minor | money }}</span>
                </div>
                <div class="row-item row-item--static">
                  <span class="dot dot--retained"></span>
                  <span class="row-item__main"
                    ><span class="row-item__title">Retained cash</span></span
                  >
                  <span class="row-item__value">{{
                    s.allocation.retained_cash_minor | money
                  }}</span>
                </div>
              </div>
              <p class="small faint">
                Retained cash is what remains of this month's net savings after transfers to savings
                accounts and investments. It is negative when older savings were spent or invested.
              </p>
              @if (s.savings_accounts.length > 0) {
                <div class="rows">
                  @for (account of s.savings_accounts; track account.account_id) {
                    <div class="row-item row-item--static">
                      <span class="row-item__main">
                        <span class="row-item__title">{{ account.name }}</span>
                        <span class="row-item__sub">
                          {{ account.inflows_minor | money }} in ·
                          {{ account.outflows_minor | money }} out
                        </span>
                      </span>
                      <span class="row-item__value" [class.pos]="account.net_minor > 0">
                        {{ account.net_minor | money: 'signed' }}
                      </span>
                    </div>
                  }
                </div>
              }
            </section>
          } @else if (savings.error()) {
            <p class="form-error">Could not load this month.</p>
          } @else {
            <div class="metrics" style="border-top: 0; padding-top: 0" aria-hidden="true">
              <span class="skeleton" style="height: 38px"></span>
              <span class="skeleton" style="height: 38px"></span>
              <span class="skeleton" style="height: 38px"></span>
            </div>
          }

          @if (trend.value(); as t) {
            <section class="section">
              <div class="section__head"><h2>Last six months</h2></div>
              <div class="trend">
                @for (point of t.months; track point.month) {
                  <div class="trend__month">
                    <div class="trend__bars">
                      <div
                        class="trend__bar trend__bar--income"
                        [style.height.%]="percent(point.income_minor, trendMax())"
                      ></div>
                      <div
                        class="trend__bar trend__bar--expense"
                        [style.height.%]="percent(point.effective_expenses_minor, trendMax())"
                      ></div>
                    </div>
                    <span class="trend__label">{{ shortMonth(point.month) }}</span>
                  </div>
                }
              </div>
              <div class="legend">
                <span class="legend__item"><span class="dot dot--income"></span>Income</span>
                <span class="legend__item"><span class="dot dot--expense"></span>Spent</span>
              </div>
              <div class="rows">
                @for (point of t.months; track point.month) {
                  <div class="row-item row-item--static" style="min-height: 40px; padding: 8px 0">
                    <span class="row-item__main"
                      ><span class="row-item__sub">{{ shortMonth(point.month) }}</span></span
                    >
                    <span class="row-item__meta">{{ rate(point.savings_rate) }}</span>
                    <span
                      class="row-item__value"
                      [class.pos]="point.net_savings_minor > 0"
                      [class.neg]="point.net_savings_minor < 0"
                    >
                      {{ point.net_savings_minor | money: 'signed' }}
                    </span>
                  </div>
                }
              </div>
            </section>
          }

          @if (expenses.value(); as e) {
            <section class="section">
              <div class="section__head">
                <h2>Spending</h2>
                <span class="section__link tnum">{{ e.total_minor | money }}</span>
              </div>
              @if (e.items.length === 0) {
                <p class="small faint">No expenses this month.</p>
              }
              <div class="rows">
                @for (item of e.items; track item.category_id) {
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
                        [style.width.%]="percent(item.effective_minor, e.items[0].effective_minor)"
                      ></div>
                    </div>
                    @if (item.reimbursed_minor > 0) {
                      <span class="small faint"
                        >{{ item.gross_minor | money }} spent,
                        {{ item.reimbursed_minor | money }} refunded</span
                      >
                    }
                  </div>
                }
              </div>
            </section>
          }

          @if (income.value(); as i) {
            @if (i.items.length > 0) {
              <section class="section">
                <div class="section__head">
                  <h2>Income</h2>
                  <span class="section__link tnum">{{ i.total_minor | money }}</span>
                </div>
                <div class="rows">
                  @for (item of i.items; track item.category_id) {
                    <div class="breakdown">
                      <div class="breakdown__line">
                        <span class="breakdown__name">
                          <app-icon [name]="item.icon" [size]="16" [strokeWidth]="1.75" />
                          <span class="truncate">{{ item.name }}</span>
                        </span>
                        <span class="tnum pos">{{ item.effective_minor | money }}</span>
                      </div>
                      <div class="bar">
                        <div
                          class="bar__fill bar__fill--pos"
                          [style.width.%]="
                            percent(item.effective_minor, i.items[0].effective_minor)
                          "
                        ></div>
                      </div>
                    </div>
                  }
                </div>
              </section>
            }
          }

          @if (investments.value(); as inv) {
            <section class="section">
              <div class="section__head">
                <h2>Investments</h2>
                <span class="section__link tnum"
                  >{{ inv.total_invested_minor | money }} all time</span
                >
              </div>
              @if (inv.by_asset.length === 0) {
                <p class="small faint">No investments recorded yet.</p>
              } @else {
                <div class="rows">
                  @for (asset of inv.by_asset; track asset.investment_asset_id) {
                    <div class="breakdown">
                      <div class="breakdown__line">
                        <span class="breakdown__name">
                          <span class="truncate">{{ asset.name }}</span>
                          <span class="faint small">{{ asset.symbol ?? asset.type }}</span>
                        </span>
                        <span class="tnum">{{ asset.invested_minor | money }}</span>
                      </div>
                      <div class="bar">
                        <div
                          class="bar__fill bar__fill--inv"
                          [style.width.%]="percent(asset.invested_minor, inv.total_invested_minor)"
                        ></div>
                      </div>
                    </div>
                  }
                </div>
                @if (periodInvestments.value(); as pi) {
                  <p class="small faint">
                    Invested this month: {{ pi.total_invested_minor | money }}
                  </p>
                }
              }
            </section>
          }
        </div>
      }
    </div>
  `,
})
export class InsightsPage {
  readonly period = inject(PeriodStore);
  private readonly reports = inject(ReportsService);

  readonly savings = this.reports.savings(() => this.period.bounds());
  readonly expenses = this.reports.categories(() => this.period.bounds(), 'EXPENSE');
  readonly income = this.reports.categories(() => this.period.bounds(), 'INCOME');
  readonly investments = this.reports.investments(() => null);
  readonly periodInvestments = this.reports.investments(() => this.period.bounds());
  readonly trend = this.reports.monthlyTrend(6, () => this.period.bounds().to);

  readonly trendMax = computed(() =>
    Math.max(
      1,
      ...(this.trend.value()?.months ?? []).flatMap((p) => [
        p.income_minor,
        p.effective_expenses_minor,
      ]),
    ),
  );

  rate(value: number | null): string {
    return formatRate(value);
  }

  percent(part: number, whole: number): number {
    if (whole <= 0) {
      return 0;
    }

    return Math.max(0, Math.min(100, (part / whole) * 100));
  }

  shortMonth(key: string): string {
    return formatShortMonth(key);
  }
}
