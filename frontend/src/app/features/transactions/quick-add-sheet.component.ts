import { NgTemplateOutlet } from '@angular/common';
import { Component, computed, effect, inject, input, model, output, signal } from '@angular/core';
import { Account, Transaction } from '../../core/api/api.models';
import { errorMessage } from '../../core/api/api-error';
import { ToastService } from '../../core/toast.service';
import { formatDate, todayIso } from '../../shared/dates';
import { IconComponent } from '../../shared/icon.component';
import { MoneyPipe } from '../../shared/money.pipe';
import { SheetComponent } from '../../shared/sheet.component';
import { AccountsService } from '../accounts/accounts.service';
import { CategoriesService } from '../categories/categories.service';
import { InvestmentAssetsService } from '../investments/investment-assets.service';
import {
  ENTRY_TYPES,
  EntryType,
  emptyForm,
  formFromTransaction,
  FormState,
  kindOf,
  toUpdatePayload,
  validateForm,
} from './transaction-form';
import { TransactionsService } from './transactions.service';

type Field = 'from' | 'to' | 'category' | 'asset' | 'expense';

const TYPE_HINTS: Record<EntryType, string> = {
  EXPENSE: 'Money spent',
  INCOME: 'Money received',
  TRANSFER: 'Between your accounts',
  SAVE: 'Into a savings account',
  INVESTMENT: 'Into an asset',
  REIMBURSEMENT: 'Money paid back for an expense',
};

/**
 * Quick Add (new transaction) and edit sheet. Two steps: pick the entry
 * type, then a form where the amount dominates and every other value is a
 * row that expands its options in place. Validation and payload building
 * live in transaction-form.ts.
 */
@Component({
  selector: 'app-quick-add-sheet',
  imports: [NgTemplateOutlet, SheetComponent, IconComponent, MoneyPipe],
  template: `
    <app-sheet [(open)]="open" [title]="sheetTitle()">
      @if (step() === 'form' && !transaction()) {
        <button
          sheet-leading
          type="button"
          class="icon-button"
          aria-label="Back"
          (click)="step.set('type')"
        >
          <app-icon name="chevron-left" [size]="20" />
        </button>
      }

      @if (step() === 'type') {
        <div class="type-list fade-in">
          @for (option of entryTypes; track option.type) {
            <button type="button" class="type-list__item" (click)="chooseType(option.type)">
              <span class="row-item__icon">
                <app-icon [name]="option.icon" [size]="17" [strokeWidth]="1.75" />
              </span>
              <span class="row-item__main">
                <span class="row-item__title">{{ option.label }}</span>
                <span class="row-item__sub">{{ hint(option.type) }}</span>
              </span>
              <app-icon class="row-item__chevron" name="chevron-right" [size]="16" />
            </button>
          }
        </div>
      } @else {
        <form class="sheet-form fade-in" (submit)="save($event)">
          <div class="amount-field">
            <span class="amount-field__currency">€</span>
            <input
              #amountInput
              class="amount-field__input"
              type="text"
              inputmode="decimal"
              autocomplete="off"
              placeholder="0.00"
              aria-label="Amount"
              [value]="form().amount"
              [style.width.ch]="amountWidth()"
              (input)="patch({ amount: amountInput.value })"
            />
          </div>

          <div class="group">
            @switch (form().type) {
              @case ('EXPENSE') {
                <ng-container *ngTemplateOutlet="categoryRow" />
                <ng-container *ngTemplateOutlet="fromRow; context: { label: 'From' }" />
              }
              @case ('INCOME') {
                <ng-container *ngTemplateOutlet="categoryRow" />
                <ng-container *ngTemplateOutlet="toRow; context: { label: 'To' }" />
              }
              @case ('TRANSFER') {
                <ng-container *ngTemplateOutlet="fromRow; context: { label: 'From' }" />
                <ng-container *ngTemplateOutlet="toRow; context: { label: 'To' }" />
              }
              @case ('SAVE') {
                <ng-container *ngTemplateOutlet="fromRow; context: { label: 'From' }" />
                <ng-container *ngTemplateOutlet="toRow; context: { label: 'To savings' }" />
              }
              @case ('INVESTMENT') {
                <ng-container *ngTemplateOutlet="fromRow; context: { label: 'From' }" />
                <ng-container *ngTemplateOutlet="assetRow" />
              }
              @case ('REIMBURSEMENT') {
                <ng-container *ngTemplateOutlet="expenseRow" />
                <ng-container *ngTemplateOutlet="toRow; context: { label: 'To' }" />
              }
            }

            <label class="form-row form-row--static">
              <span class="form-row__label">Date</span>
              <input
                #dateInput
                class="form-row__input"
                type="date"
                [value]="form().date"
                (input)="patch({ date: dateInput.value })"
              />
            </label>

            <label class="form-row form-row--static">
              <span class="form-row__label">Note</span>
              <input
                #descriptionInput
                class="form-row__input"
                type="text"
                maxlength="500"
                autocomplete="off"
                placeholder="Optional"
                [value]="form().description"
                (input)="patch({ description: descriptionInput.value })"
              />
            </label>
          </div>

          @if (error()) {
            <p class="form-error error-in" role="alert">{{ error() }}</p>
          }

          <div class="sheet-form__actions">
            @if (transaction(); as editing) {
              <button
                type="button"
                class="btn btn--danger"
                [disabled]="busy()"
                (click)="remove(editing)"
              >
                Delete
              </button>
            }
            <button type="submit" class="btn btn--primary grow" [disabled]="busy()">
              {{ transaction() ? 'Save changes' : 'Add ' + typeLabel().toLowerCase() }}
            </button>
          </div>
        </form>
      }
    </app-sheet>

    <!-- Row templates: label on the left, chosen value on the right, options expand below. -->

    <ng-template #fromRow let-label="label">
      <button type="button" class="form-row" (click)="toggle('from')">
        <span class="form-row__label">{{ label }}</span>
        <span class="form-row__value" [class.form-row__value--placeholder]="!fromName()">
          {{ fromName() || 'Choose account' }}
        </span>
        <app-icon
          class="chevron row-item__chevron"
          [class.chevron--open]="expanded() === 'from'"
          name="chevron-right"
          [size]="16"
        />
      </button>
      @if (expanded() === 'from') {
        <div class="form-expand">
          <div class="chips">
            @for (account of fromOptions(); track account.id) {
              <button
                type="button"
                class="chip"
                [class.chip--on]="form().fromAccountId === account.id"
                (click)="choose({ fromAccountId: account.id })"
              >
                {{ account.name }}
              </button>
            }
          </div>
          @if (fromOptions().length === 0) {
            <p class="notice">No accounts yet. Create one in Settings.</p>
          }
        </div>
      }
    </ng-template>

    <ng-template #toRow let-label="label">
      <button type="button" class="form-row" (click)="toggle('to')">
        <span class="form-row__label">{{ label }}</span>
        <span class="form-row__value" [class.form-row__value--placeholder]="!toName()">
          {{ toName() || 'Choose account' }}
        </span>
        <app-icon
          class="chevron row-item__chevron"
          [class.chevron--open]="expanded() === 'to'"
          name="chevron-right"
          [size]="16"
        />
      </button>
      @if (expanded() === 'to') {
        <div class="form-expand">
          <div class="chips">
            @for (account of toOptions(); track account.id) {
              <button
                type="button"
                class="chip"
                [class.chip--on]="form().toAccountId === account.id"
                (click)="choose({ toAccountId: account.id })"
              >
                {{ account.name }}
              </button>
            }
          </div>
          @if (toOptions().length === 0) {
            <p class="notice">
              {{
                form().type === 'SAVE'
                  ? 'Create an account of type Savings in Settings first.'
                  : 'No accounts yet. Create one in Settings.'
              }}
            </p>
          }
        </div>
      }
    </ng-template>

    <ng-template #categoryRow>
      <button type="button" class="form-row" (click)="toggle('category')">
        <span class="form-row__label">Category</span>
        <span class="form-row__value" [class.form-row__value--placeholder]="!categoryName()">
          {{ categoryName() || 'Choose category' }}
        </span>
        <app-icon
          class="chevron row-item__chevron"
          [class.chevron--open]="expanded() === 'category'"
          name="chevron-right"
          [size]="16"
        />
      </button>
      @if (expanded() === 'category') {
        <div class="form-expand">
          <div class="icon-grid">
            @for (category of categoryOptions(); track category.id) {
              <button
                type="button"
                class="icon-tile"
                [class.icon-tile--on]="form().categoryId === category.id"
                (click)="choose({ categoryId: category.id })"
              >
                <app-icon [name]="category.icon" [size]="20" [strokeWidth]="1.75" />
                <span class="icon-tile__label">{{ category.name }}</span>
              </button>
            }
          </div>
          @if (categoryOptions().length === 0) {
            <p class="notice">No categories of this kind yet. Add one in Settings.</p>
          }
        </div>
      }
    </ng-template>

    <ng-template #assetRow>
      <button type="button" class="form-row" (click)="toggle('asset')">
        <span class="form-row__label">Asset</span>
        <span class="form-row__value" [class.form-row__value--placeholder]="!assetName()">
          {{ assetName() || 'Choose asset' }}
        </span>
        <app-icon
          class="chevron row-item__chevron"
          [class.chevron--open]="expanded() === 'asset'"
          name="chevron-right"
          [size]="16"
        />
      </button>
      @if (expanded() === 'asset') {
        <div class="form-expand">
          <div class="chips">
            @for (asset of assets.active(); track asset.id) {
              <button
                type="button"
                class="chip"
                [class.chip--on]="form().investmentAssetId === asset.id"
                (click)="choose({ investmentAssetId: asset.id })"
              >
                {{ asset.name }}
                @if (asset.symbol) {
                  <span class="faint">{{ asset.symbol }}</span>
                }
              </button>
            }
          </div>
          @if (assets.active().length === 0) {
            <p class="notice">No investment assets yet. Add one in Settings.</p>
          }
        </div>
      }
    </ng-template>

    <ng-template #expenseRow>
      <button type="button" class="form-row" (click)="toggle('expense')">
        <span class="form-row__label">Expense</span>
        <span class="form-row__value" [class.form-row__value--placeholder]="!expenseName()">
          {{ expenseName() || 'Choose expense' }}
        </span>
        <app-icon
          class="chevron row-item__chevron"
          [class.chevron--open]="expanded() === 'expense'"
          name="chevron-right"
          [size]="16"
        />
      </button>
      @if (expanded() === 'expense') {
        <div class="form-expand">
          <div class="rows">
            @for (expense of refundableExpenses(); track expense.id) {
              <button
                type="button"
                class="row-item"
                [style.opacity]="
                  form().reimbursesTransactionId && form().reimbursesTransactionId !== expense.id
                    ? 0.5
                    : 1
                "
                (click)="choose({ reimbursesTransactionId: expense.id })"
              >
                <span class="row-item__main">
                  <span class="row-item__title truncate">{{ expenseTitle(expense) }}</span>
                  <span class="row-item__sub">
                    {{ formatDate(expense.occurred_on) }} ·
                    {{ expense.amount_minor - expense.reimbursed_amount_minor | money }} left
                  </span>
                </span>
                <span class="row-item__value">{{ expense.amount_minor | money }}</span>
              </button>
            }
          </div>
          @if (refundableExpenses().length === 0) {
            <p class="notice">No recent expenses left to refund.</p>
          }
        </div>
      }
    </ng-template>
  `,
})
export class QuickAddSheetComponent {
  readonly accounts = inject(AccountsService);
  readonly categories = inject(CategoriesService);
  readonly assets = inject(InvestmentAssetsService);
  private readonly transactions = inject(TransactionsService);
  private readonly toasts = inject(ToastService);

  readonly open = model(false);
  /** When set, the sheet edits this transaction instead of creating one. */
  readonly transaction = input<Transaction | null>(null);
  readonly saved = output<Transaction>();
  readonly deleted = output<string>();

  readonly entryTypes = ENTRY_TYPES;
  readonly formatDate = formatDate;

  readonly step = signal<'type' | 'form'>('type');
  readonly expanded = signal<Field | null>(null);
  readonly form = signal<FormState>(emptyForm('EXPENSE', todayIso()));
  readonly error = signal<string | null>(null);
  readonly busy = signal(false);

  private readonly recentExpenses = this.transactions.page(
    () => ({ kind: 'EXPENSE' }),
    () => 40,
  );

  readonly refundableExpenses = computed(() =>
    (this.recentExpenses.value()?.items ?? []).filter(
      (expense) =>
        expense.reimbursed_amount_minor < expense.amount_minor ||
        expense.id === this.form().reimbursesTransactionId,
    ),
  );

  readonly typeLabel = computed(
    () => ENTRY_TYPES.find((option) => option.type === this.form().type)?.label ?? '',
  );

  readonly sheetTitle = computed(() => {
    if (this.transaction()) {
      return `Edit ${this.typeLabel().toLowerCase()}`;
    }

    return this.step() === 'type' ? 'New' : this.typeLabel();
  });

  readonly amountWidth = computed(() => Math.max(4, this.form().amount.length + 1));

  private readonly savingsAccounts = computed(() =>
    this.accounts.active().filter((account) => account.type === 'SAVINGS'),
  );

  private readonly nonSavingsAccounts = computed(() =>
    this.accounts.active().filter((account) => account.type !== 'SAVINGS'),
  );

  readonly fromOptions = computed(() =>
    this.form().type === 'SAVE' ? this.nonSavingsAccounts() : this.accounts.active(),
  );

  readonly toOptions = computed(() => {
    const type = this.form().type;

    if (type === 'SAVE') {
      return this.savingsAccounts();
    }

    if (type === 'TRANSFER') {
      return this.accounts.active().filter((account) => account.id !== this.form().fromAccountId);
    }

    return this.accounts.active();
  });

  readonly categoryOptions = computed(() =>
    this.form().type === 'INCOME'
      ? this.categories.activeIncome()
      : this.categories.activeExpense(),
  );

  readonly fromName = computed(() => this.accountName(this.form().fromAccountId));
  readonly toName = computed(() => this.accountName(this.form().toAccountId));
  readonly categoryName = computed(() => {
    const id = this.form().categoryId;
    return id ? (this.categories.byId().get(id)?.name ?? '') : '';
  });
  readonly assetName = computed(() => {
    const id = this.form().investmentAssetId;
    return id ? (this.assets.byId().get(id)?.name ?? '') : '';
  });
  readonly expenseName = computed(() => {
    const id = this.form().reimbursesTransactionId;
    const expense = this.refundableExpenses().find((item) => item.id === id);
    return expense ? this.expenseTitle(expense) : '';
  });

  constructor() {
    // Reset every time the sheet opens, prefilled when editing.
    effect(() => {
      if (!this.open()) {
        return;
      }

      const editing = this.transaction();
      this.error.set(null);
      this.busy.set(false);
      this.expanded.set(null);
      this.step.set(editing ? 'form' : 'type');
      this.form.set(
        editing
          ? formFromTransaction(editing, this.accounts.byId())
          : this.withDefaults(emptyForm('EXPENSE', todayIso())),
      );
    });
  }

  hint(type: EntryType): string {
    return TYPE_HINTS[type];
  }

  chooseType(type: EntryType): void {
    this.form.set(this.withDefaults(emptyForm(type, this.form().date), this.form().amount));
    this.error.set(null);
    this.expanded.set(null);
    this.step.set('form');
  }

  toggle(field: Field): void {
    this.expanded.update((current) => (current === field ? null : field));
  }

  patch(changes: Partial<FormState>): void {
    this.form.update((state) => ({ ...state, ...changes }));
    this.error.set(null);
  }

  /** Pick an option and collapse the row. */
  choose(changes: Partial<FormState>): void {
    this.patch(changes);
    this.expanded.set(null);
  }

  expenseTitle(expense: Transaction): string {
    return (
      expense.description ??
      (expense.category_id ? this.categories.byId().get(expense.category_id)?.name : null) ??
      'Expense'
    );
  }

  async save(event: Event): Promise<void> {
    event.preventDefault();

    const { payload, error } = validateForm(this.form());

    if (!payload) {
      this.error.set(error);
      return;
    }

    this.busy.set(true);

    try {
      const editing = this.transaction();
      const saved = editing
        ? await this.transactions.update(editing.id, toUpdatePayload(payload))
        : await this.transactions.create(payload);

      this.saved.emit(saved);
      this.open.set(false);
      this.toasts.show(editing ? 'Changes saved' : `${this.typeLabel()} added`);
    } catch (failure) {
      this.error.set(errorMessage(failure));
    } finally {
      this.busy.set(false);
    }
  }

  async remove(editing: Transaction): Promise<void> {
    if (!confirm('Delete this transaction?')) {
      return;
    }

    this.busy.set(true);

    try {
      await this.transactions.delete(editing.id);
      this.deleted.emit(editing.id);
      this.open.set(false);
      this.toasts.show('Transaction deleted', 'neutral');
    } catch (failure) {
      this.error.set(errorMessage(failure));
    } finally {
      this.busy.set(false);
    }
  }

  private accountName(id: string | null): string {
    return id ? (this.accounts.byId().get(id)?.name ?? '') : '';
  }

  /** Preselect the only sensible choice so a common entry is two taps. */
  private withDefaults(state: FormState, amount = ''): FormState {
    const active = this.accounts.active();
    const single = (accounts: Account[]) => (accounts.length === 1 ? accounts[0].id : null);
    const kind = kindOf(state.type);

    return {
      ...state,
      amount,
      fromAccountId:
        kind === 'INCOME' || kind === 'REIMBURSEMENT'
          ? null
          : single(state.type === 'SAVE' ? this.nonSavingsAccounts() : active),
      toAccountId:
        state.type === 'SAVE'
          ? single(this.savingsAccounts())
          : kind === 'INCOME' || kind === 'REIMBURSEMENT'
            ? single(active)
            : null,
    };
  }
}
