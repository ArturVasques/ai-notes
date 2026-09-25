import { Component, computed, inject, input, output } from '@angular/core';
import { Transaction } from '../../core/api/api.models';
import { IconComponent } from '../../shared/icon.component';
import { MoneyPipe } from '../../shared/money.pipe';
import { AccountsService } from '../accounts/accounts.service';
import { CategoriesService } from '../categories/categories.service';
import { InvestmentAssetsService } from '../investments/investment-assets.service';

const KIND_ICONS: Record<Transaction['kind'], string> = {
  EXPENSE: 'arrow-up-right',
  INCOME: 'arrow-down-left',
  TRANSFER: 'arrow-left-right',
  INVESTMENT: 'chart-candlestick',
  REIMBURSEMENT: 'undo-2',
};

/** One row of activity: discreet icon, title and context, amount right. */
@Component({
  selector: 'app-transaction-item',
  imports: [IconComponent],
  template: `
    <button type="button" class="row-item" (click)="selected.emit(transaction())">
      <span
        class="row-item__icon"
        [class.row-item__icon--inv]="transaction().kind === 'INVESTMENT'"
      >
        <app-icon [name]="icon()" [size]="17" [strokeWidth]="1.75" />
      </span>
      <span class="row-item__main">
        <span class="row-item__title truncate">{{ title() }}</span>
        <span class="row-item__sub truncate">{{ subtitle() }}</span>
      </span>
      <span class="row-item__value" [class]="'row-item__value ' + amountClass()">
        {{ amountText() }}
      </span>
    </button>
  `,
})
export class TransactionItemComponent {
  private readonly accounts = inject(AccountsService);
  private readonly categories = inject(CategoriesService);
  private readonly assets = inject(InvestmentAssetsService);
  private readonly money = new MoneyPipe();

  readonly transaction = input.required<Transaction>();
  readonly selected = output<Transaction>();

  private readonly category = computed(() => {
    const id = this.transaction().category_id;
    return id ? this.categories.byId().get(id) : undefined;
  });

  private readonly asset = computed(() => {
    const id = this.transaction().investment_asset_id;
    return id ? this.assets.byId().get(id) : undefined;
  });

  readonly icon = computed(() => this.category()?.icon ?? KIND_ICONS[this.transaction().kind]);

  readonly title = computed(() => {
    const transaction = this.transaction();

    if (transaction.description) {
      return transaction.description;
    }

    switch (transaction.kind) {
      case 'INVESTMENT':
        return this.asset()?.name ?? 'Investment';
      case 'TRANSFER':
        return 'Transfer';
      case 'REIMBURSEMENT':
        return 'Refund';
      default:
        return this.category()?.name ?? transaction.kind;
    }
  });

  readonly subtitle = computed(() => {
    const transaction = this.transaction();
    const from = this.accountName(transaction.from_account_id);
    const to = this.accountName(transaction.to_account_id);

    switch (transaction.kind) {
      case 'EXPENSE':
        return [this.category()?.name, from].filter(Boolean).join(' · ');
      case 'INCOME':
        return [this.category()?.name, to].filter(Boolean).join(' · ');
      case 'TRANSFER':
        return `${from} → ${to}`;
      case 'INVESTMENT':
        return `${from} → ${this.asset()?.name ?? 'asset'}`;
      case 'REIMBURSEMENT':
        return `Refund · ${to}`;
    }
  });

  readonly amountClass = computed(() => {
    switch (this.transaction().kind) {
      case 'INCOME':
      case 'REIMBURSEMENT':
        return 'pos';
      case 'INVESTMENT':
        return 'inv';
      case 'TRANSFER':
        return 'muted';
      default:
        return '';
    }
  });

  readonly amountText = computed(() => {
    const transaction = this.transaction();

    switch (transaction.kind) {
      case 'EXPENSE':
        return this.money.transform(-transaction.amount_minor);
      case 'INCOME':
      case 'REIMBURSEMENT':
        return this.money.transform(transaction.amount_minor, 'signed');
      default:
        return this.money.transform(transaction.amount_minor);
    }
  });

  private accountName(id: string | null): string {
    return id ? (this.accounts.byId().get(id)?.name ?? 'Account') : '';
  }
}
