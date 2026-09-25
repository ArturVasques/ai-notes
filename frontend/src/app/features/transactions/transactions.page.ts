import { Component, computed, inject, signal } from '@angular/core';
import { Transaction, TransactionFilters, TransactionKind } from '../../core/api/api.models';
import { errorMessage } from '../../core/api/api-error';
import { PeriodStore } from '../../core/period.store';
import { IconComponent } from '../../shared/icon.component';
import { MonthSwitcherComponent } from '../../shared/month-switcher.component';
import { SheetComponent } from '../../shared/sheet.component';
import { AccountsService } from '../accounts/accounts.service';
import { CategoriesService } from '../categories/categories.service';
import { QuickAddSheetComponent } from './quick-add-sheet.component';
import { TransactionItemComponent } from './transaction-item.component';
import { groupByDay } from './transaction-grouping';
import { TransactionsService } from './transactions.service';

const KINDS: { kind: TransactionKind; label: string }[] = [
  { kind: 'EXPENSE', label: 'Expenses' },
  { kind: 'INCOME', label: 'Income' },
  { kind: 'TRANSFER', label: 'Transfers' },
  { kind: 'INVESTMENT', label: 'Investments' },
  { kind: 'REIMBURSEMENT', label: 'Refunds' },
];

const PAGE_SIZE = 50;

@Component({
  selector: 'app-transactions-page',
  imports: [
    IconComponent,
    MonthSwitcherComponent,
    SheetComponent,
    TransactionItemComponent,
    QuickAddSheetComponent,
  ],
  template: `
    <div class="page">
      <app-month-switcher eyebrow="Activity">
        <button
          type="button"
          class="icon-button glass-control"
          [class.icon-button--on]="activeFilterCount() > 0"
          aria-label="Filters"
          (click)="filtersOpen.set(true)"
        >
          <app-icon name="filter" [size]="18" />
        </button>
      </app-month-switcher>

      @if (activeFilterCount() > 0) {
        <div class="chips fade-in">
          @if (kind(); as k) {
            <button type="button" class="chip chip--on" (click)="kind.set(null)">
              {{ kindLabel(k) }} <app-icon name="x" [size]="14" />
            </button>
          }
          @if (categoryId(); as id) {
            <button type="button" class="chip chip--on" (click)="categoryId.set(null)">
              {{ categories.byId().get(id)?.name }} <app-icon name="x" [size]="14" />
            </button>
          }
          @if (accountId(); as id) {
            <button type="button" class="chip chip--on" (click)="accountId.set(null)">
              {{ accounts.byId().get(id)?.name }} <app-icon name="x" [size]="14" />
            </button>
          }
        </div>
      }

      @for (key of [viewKey()]; track key) {
        <div class="stack fade-in" style="gap: var(--s-6)">
          @if (firstPage.isLoading() && groups().length === 0) {
            <div class="rows" aria-hidden="true">
              <span class="skeleton" style="width: 80px; height: 12px; margin-bottom: 10px"></span>
              <span class="skeleton" style="height: 54px; margin: 6px 0"></span>
              <span class="skeleton" style="height: 54px; margin: 6px 0"></span>
              <span class="skeleton" style="height: 54px; margin: 6px 0"></span>
            </div>
          } @else if (firstPage.error()) {
            <p class="form-error">{{ message(firstPage.error()) }}</p>
          } @else if (groups().length === 0) {
            <div class="empty">
              <p class="empty__title">No activity</p>
              <p>Nothing matches this month and these filters.</p>
            </div>
          } @else {
            @for (group of groups(); track group.date) {
              <div class="rows">
                <div class="day">{{ group.label }}</div>
                @for (transaction of group.items; track transaction.id) {
                  <app-transaction-item [transaction]="transaction" (selected)="edit($event)" />
                }
              </div>
            }
            @if (nextCursor()) {
              <button
                type="button"
                class="btn btn--quiet"
                [disabled]="loadingMore()"
                (click)="loadMore()"
              >
                {{ loadingMore() ? 'Loading…' : 'Load more' }}
              </button>
            }
          }
        </div>
      }

      <app-sheet [(open)]="filtersOpen" title="Filters">
        <div class="sheet-form">
          <div class="stack" style="gap: var(--s-2)">
            <span class="eyebrow">Type</span>
            <div class="chips">
              @for (option of kinds; track option.kind) {
                <button
                  type="button"
                  class="chip"
                  [class.chip--on]="kind() === option.kind"
                  (click)="kind.set(kind() === option.kind ? null : option.kind)"
                >
                  {{ option.label }}
                </button>
              }
            </div>
          </div>
          <div class="group">
            <button type="button" class="form-row" (click)="toggleFilter('category')">
              <span class="form-row__label">Category</span>
              <span class="form-row__value" [class.form-row__value--placeholder]="!categoryId()">
                {{ categoryId() ? categories.byId().get(categoryId()!)?.name : 'Any' }}
              </span>
              <app-icon
                class="chevron row-item__chevron"
                [class.chevron--open]="expandedFilter() === 'category'"
                name="chevron-right"
                [size]="16"
              />
            </button>
            @if (expandedFilter() === 'category') {
              <div class="form-expand">
                <div class="chips">
                  <button
                    type="button"
                    class="chip"
                    [class.chip--on]="!categoryId()"
                    (click)="pickCategory(null)"
                  >
                    Any
                  </button>
                  @for (category of categories.active(); track category.id) {
                    <button
                      type="button"
                      class="chip"
                      [class.chip--on]="categoryId() === category.id"
                      (click)="pickCategory(category.id)"
                    >
                      {{ category.name }}
                    </button>
                  }
                </div>
              </div>
            }
            <button type="button" class="form-row" (click)="toggleFilter('account')">
              <span class="form-row__label">Account</span>
              <span class="form-row__value" [class.form-row__value--placeholder]="!accountId()">
                {{ accountId() ? accounts.byId().get(accountId()!)?.name : 'Any' }}
              </span>
              <app-icon
                class="chevron row-item__chevron"
                [class.chevron--open]="expandedFilter() === 'account'"
                name="chevron-right"
                [size]="16"
              />
            </button>
            @if (expandedFilter() === 'account') {
              <div class="form-expand">
                <div class="chips">
                  <button
                    type="button"
                    class="chip"
                    [class.chip--on]="!accountId()"
                    (click)="pickAccount(null)"
                  >
                    Any
                  </button>
                  @for (account of accounts.all.value(); track account.id) {
                    <button
                      type="button"
                      class="chip"
                      [class.chip--on]="accountId() === account.id"
                      (click)="pickAccount(account.id)"
                    >
                      {{ account.name }}
                    </button>
                  }
                </div>
              </div>
            }
          </div>
          <div class="sheet-form__actions">
            <button type="button" class="btn btn--quiet" (click)="clearFilters()">Clear</button>
            <button type="button" class="btn btn--primary grow" (click)="filtersOpen.set(false)">
              Done
            </button>
          </div>
        </div>
      </app-sheet>

      <app-quick-add-sheet [(open)]="editOpen" [transaction]="editing()" />
    </div>
  `,
})
export class TransactionsPage {
  readonly accounts = inject(AccountsService);
  readonly categories = inject(CategoriesService);
  private readonly period = inject(PeriodStore);
  private readonly transactions = inject(TransactionsService);

  readonly kinds = KINDS;
  readonly kind = signal<TransactionKind | null>(null);
  readonly categoryId = signal<string | null>(null);
  readonly accountId = signal<string | null>(null);
  readonly filtersOpen = signal(false);

  readonly filters = computed<TransactionFilters>(() => ({
    from: this.period.bounds().from,
    to: this.period.bounds().to,
    kind: this.kind() ?? undefined,
    category_id: this.categoryId() ?? undefined,
    account_id: this.accountId() ?? undefined,
  }));

  /** Re-mounts the list (with its entrance animation) when the query changes. */
  readonly viewKey = computed(() => JSON.stringify(this.filters()));

  readonly activeFilterCount = computed(
    () => [this.kind(), this.categoryId(), this.accountId()].filter(Boolean).length,
  );

  readonly firstPage = this.transactions.page(
    () => this.filters(),
    () => PAGE_SIZE,
  );

  /** Pages after the first, reset whenever the first page changes. */
  private readonly extraPages = signal<{
    key: string;
    items: Transaction[];
    cursor: string | null;
  }>({
    key: '',
    items: [],
    cursor: null,
  });

  readonly loadingMore = signal(false);

  private readonly pageKey = computed(() => this.viewKey() + this.firstPage.status());

  readonly allItems = computed(() => {
    const first = this.firstPage.value()?.items ?? [];
    const extra = this.extraPages();
    return extra.key === this.pageKey() ? [...first, ...extra.items] : first;
  });

  readonly nextCursor = computed(() => {
    const extra = this.extraPages();
    return extra.key === this.pageKey()
      ? extra.cursor
      : (this.firstPage.value()?.next_cursor ?? null);
  });

  readonly groups = computed(() => groupByDay(this.allItems()));

  readonly editing = signal<Transaction | null>(null);
  readonly editOpen = signal(false);

  kindLabel(kind: TransactionKind): string {
    return KINDS.find((option) => option.kind === kind)?.label ?? kind;
  }

  message(error: unknown): string {
    return errorMessage(error);
  }

  readonly expandedFilter = signal<'category' | 'account' | null>(null);

  toggleFilter(field: 'category' | 'account'): void {
    this.expandedFilter.update((current) => (current === field ? null : field));
  }

  pickCategory(id: string | null): void {
    this.categoryId.set(id);
    this.expandedFilter.set(null);
  }

  pickAccount(id: string | null): void {
    this.accountId.set(id);
    this.expandedFilter.set(null);
  }

  clearFilters(): void {
    this.kind.set(null);
    this.categoryId.set(null);
    this.accountId.set(null);
    this.expandedFilter.set(null);
  }

  async loadMore(): Promise<void> {
    const cursor = this.nextCursor();

    if (!cursor || this.loadingMore()) {
      return;
    }

    this.loadingMore.set(true);
    const key = this.pageKey();

    try {
      const page = await this.transactions.loadMore(this.filters(), cursor, PAGE_SIZE);
      const previous = this.extraPages();
      const items = previous.key === key ? previous.items : [];
      this.extraPages.set({ key, items: [...items, ...page.items], cursor: page.next_cursor });
    } finally {
      this.loadingMore.set(false);
    }
  }

  edit(transaction: Transaction): void {
    this.editing.set(transaction);
    this.editOpen.set(true);
  }
}
