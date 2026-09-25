import { Component, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Account, AccountType } from '../../core/api/api.models';
import { errorMessage } from '../../core/api/api-error';
import { ToastService } from '../../core/toast.service';
import { IconComponent } from '../../shared/icon.component';
import { minorToInput, parseAmountToMinor, splitMinor } from '../../shared/money';
import { MoneyPipe } from '../../shared/money.pipe';
import { SheetComponent } from '../../shared/sheet.component';
import { AccountsService } from './accounts.service';

const ACCOUNT_TYPES: { type: AccountType; label: string }[] = [
  { type: 'CHECKING', label: 'Current account' },
  { type: 'SAVINGS', label: 'Savings account' },
  { type: 'CASH', label: 'Cash' },
  { type: 'BENEFITS', label: 'Benefits (meal card, …)' },
  { type: 'BROKERAGE', label: 'Broker cash' },
];

interface AccountForm {
  name: string;
  type: AccountType;
  description: string;
  openingBalance: string;
}

@Component({
  selector: 'app-accounts-page',
  imports: [RouterLink, IconComponent, MoneyPipe, SheetComponent],
  template: `
    <div class="page">
      <div class="page-head">
        <div class="page-head__titles">
          <a class="back" routerLink="/settings"
            ><app-icon name="chevron-left" [size]="16" /> Settings</a
          >
          <h1>Accounts</h1>
        </div>
        <div class="page-head__tools">
          <button type="button" class="btn btn--small btn--primary" (click)="openNew()">
            <app-icon name="plus" [size]="14" /> Add
          </button>
        </div>
      </div>

      @if (balances.value(); as b) {
        <div class="hero fade-in">
          <span class="hero__label">Total balance</span>
          <div class="hero__value" [class.neg]="b.total_minor < 0">
            {{ parts(b.total_minor).sign }}€{{ parts(b.total_minor).units
            }}<span class="hero__cents">.{{ parts(b.total_minor).cents }}</span>
          </div>
        </div>

        @if (b.items.length === 0) {
          <div class="empty">
            <p class="empty__title">No accounts yet</p>
            <p>Create your current account, savings, meal card or cash.</p>
          </div>
        } @else {
          <div class="group fade-in">
            @for (item of b.items; track item.account.id) {
              <button type="button" class="row-item" (click)="openEdit(item.account)">
                <span class="row-item__icon">
                  <app-icon [name]="typeIcon(item.account.type)" [size]="17" [strokeWidth]="1.75" />
                </span>
                <span class="row-item__main">
                  <span class="row-item__title">
                    {{ item.account.name }}
                    @if (item.account.archived_at) {
                      <span class="badge">Archived</span>
                    }
                  </span>
                  <span class="row-item__sub">{{ typeLabel(item.account.type) }}</span>
                </span>
                <span class="row-item__value" [class.neg]="item.balance_minor < 0">
                  {{ item.balance_minor | money }}
                </span>
              </button>
            }
          </div>
        }
        <button
          type="button"
          class="btn btn--quiet btn--small"
          (click)="showArchived.set(!showArchived())"
        >
          {{ showArchived() ? 'Hide archived' : 'Show archived' }}
        </button>
      } @else {
        <div class="stack" aria-hidden="true">
          <span class="skeleton" style="width: 180px; height: 44px"></span>
          <span class="skeleton" style="height: 54px"></span>
          <span class="skeleton" style="height: 54px"></span>
        </div>
      }

      <app-sheet [(open)]="sheetOpen" [title]="editing() ? 'Edit account' : 'New account'">
        <form class="sheet-form" (submit)="save($event)">
          <div class="group">
            <label class="form-row form-row--static">
              <span class="form-row__label">Name</span>
              <input
                #name
                class="form-row__input"
                type="text"
                maxlength="100"
                placeholder="Current account"
                [value]="form().name"
                (input)="patch({ name: name.value })"
              />
            </label>
            <button type="button" class="form-row" (click)="typeOpen.set(!typeOpen())">
              <span class="form-row__label">Type</span>
              <span class="form-row__value">{{ typeLabel(form().type) }}</span>
              <app-icon
                class="chevron row-item__chevron"
                [class.chevron--open]="typeOpen()"
                name="chevron-right"
                [size]="16"
              />
            </button>
            @if (typeOpen()) {
              <div class="form-expand">
                <div class="chips">
                  @for (option of types; track option.type) {
                    <button
                      type="button"
                      class="chip"
                      [class.chip--on]="form().type === option.type"
                      (click)="patch({ type: option.type }); typeOpen.set(false)"
                    >
                      {{ option.label }}
                    </button>
                  }
                </div>
              </div>
            }
            <label class="form-row form-row--static">
              <span class="form-row__label">Opening</span>
              <input
                #opening
                class="form-row__input"
                type="text"
                inputmode="decimal"
                placeholder="0.00"
                [value]="form().openingBalance"
                (input)="patch({ openingBalance: opening.value })"
              />
            </label>
            <label class="form-row form-row--static">
              <span class="form-row__label">Note</span>
              <input
                #description
                class="form-row__input"
                type="text"
                maxlength="500"
                placeholder="Optional"
                [value]="form().description"
                (input)="patch({ description: description.value })"
              />
            </label>
          </div>
          <p class="group__footer" style="padding-top: 0">
            The opening balance is the balance before the first recorded transaction. Use a minus
            sign for an overdraft.
          </p>
          @if (error()) {
            <p class="form-error error-in" role="alert">{{ error() }}</p>
          }
          <div class="sheet-form__actions">
            @if (editing(); as account) {
              <button
                type="button"
                class="btn btn--quiet"
                [disabled]="busy()"
                (click)="toggleArchive(account)"
              >
                {{ account.archived_at ? 'Restore' : 'Archive' }}
              </button>
            }
            <button type="submit" class="btn btn--primary grow" [disabled]="busy()">
              {{ editing() ? 'Save changes' : 'Add account' }}
            </button>
          </div>
        </form>
      </app-sheet>
    </div>
  `,
})
export class AccountsPage {
  private readonly accounts = inject(AccountsService);
  private readonly toasts = inject(ToastService);

  readonly types = ACCOUNT_TYPES;
  readonly showArchived = signal(false);
  readonly balances = this.accounts.balances(() => this.showArchived());

  readonly sheetOpen = signal(false);
  readonly typeOpen = signal(false);
  readonly editing = signal<Account | null>(null);
  readonly form = signal<AccountForm>({
    name: '',
    type: 'CHECKING',
    description: '',
    openingBalance: '',
  });
  readonly error = signal<string | null>(null);
  readonly busy = signal(false);

  parts(minor: number) {
    return splitMinor(minor);
  }

  typeLabel(type: AccountType): string {
    return ACCOUNT_TYPES.find((option) => option.type === type)?.label ?? type;
  }

  typeIcon(type: AccountType): string {
    switch (type) {
      case 'SAVINGS':
        return 'piggy-bank';
      case 'CASH':
        return 'banknote';
      case 'BENEFITS':
        return 'credit-card';
      case 'BROKERAGE':
        return 'chart-candlestick';
      default:
        return 'landmark';
    }
  }

  openNew(): void {
    this.editing.set(null);
    this.form.set({ name: '', type: 'CHECKING', description: '', openingBalance: '' });
    this.error.set(null);
    this.typeOpen.set(false);
    this.sheetOpen.set(true);
  }

  openEdit(account: Account): void {
    this.editing.set(account);
    this.form.set({
      name: account.name,
      type: account.type,
      description: account.description ?? '',
      openingBalance:
        account.opening_balance_minor === 0
          ? ''
          : `${account.opening_balance_minor < 0 ? '-' : ''}${minorToInput(account.opening_balance_minor)}`,
    });
    this.error.set(null);
    this.typeOpen.set(false);
    this.sheetOpen.set(true);
  }

  patch(changes: Partial<AccountForm>): void {
    this.form.update((state) => ({ ...state, ...changes }));
    this.error.set(null);
  }

  async save(event: Event): Promise<void> {
    event.preventDefault();

    const state = this.form();
    const name = state.name.trim();
    const opening = parseOpeningBalance(state.openingBalance);

    if (!name) {
      this.error.set('Enter a name.');
      return;
    }

    if (opening === null) {
      this.error.set('The opening balance must be an amount with up to two decimals.');
      return;
    }

    this.busy.set(true);

    try {
      const editing = this.editing();
      const body = {
        name,
        type: state.type,
        description: state.description.trim() || null,
        opening_balance_minor: opening,
      };

      if (editing) {
        await this.accounts.update(editing.id, body);
      } else {
        await this.accounts.create(body);
      }

      this.sheetOpen.set(false);
      this.toasts.show(editing ? 'Account updated' : 'Account added');
    } catch (failure) {
      this.error.set(errorMessage(failure));
    } finally {
      this.busy.set(false);
    }
  }

  async toggleArchive(account: Account): Promise<void> {
    this.busy.set(true);

    try {
      await this.accounts.update(account.id, { archived: !account.archived_at });
      this.sheetOpen.set(false);
      this.toasts.show(account.archived_at ? 'Account restored' : 'Account archived', 'neutral');
    } catch (failure) {
      this.error.set(errorMessage(failure));
    } finally {
      this.busy.set(false);
    }
  }
}

/** "" → 0, "-12.50" → -1250, invalid → null. */
function parseOpeningBalance(input: string): number | null {
  const text = input.trim();

  if (text === '') {
    return 0;
  }

  const negative = text.startsWith('-');
  const minor = parseAmountToMinor(negative ? text.slice(1) : text);

  if (minor === null) {
    return /^-?0+([.,]0{1,2})?$/.test(text) ? 0 : null;
  }

  return negative ? -minor : minor;
}
