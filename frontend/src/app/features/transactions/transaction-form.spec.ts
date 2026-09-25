import { Account, Transaction } from '../../core/api/api.models';
import {
  emptyForm,
  formFromTransaction,
  kindOf,
  toUpdatePayload,
  validateForm,
} from './transaction-form';

const CURRENT = 'a1';
const SAVINGS = 'a2';
const CATEGORY = 'c1';

function account(id: string, type: Account['type']): Account {
  return {
    id,
    name: id,
    type,
    description: null,
    currency: 'EUR',
    opening_balance_minor: 0,
    archived_at: null,
    created_at: '2026-09-01T00:00:00Z',
  };
}

const accounts = new Map([
  [CURRENT, account(CURRENT, 'CHECKING')],
  [SAVINGS, account(SAVINGS, 'SAVINGS')],
]);

describe('transaction form', () => {
  it('maps Save to a transfer', () => {
    expect(kindOf('SAVE')).toBe('TRANSFER');
    expect(kindOf('EXPENSE')).toBe('EXPENSE');
  });

  it('builds an expense payload in minor units', () => {
    const result = validateForm({
      ...emptyForm('EXPENSE', '2026-09-25'),
      amount: '24,80',
      description: '  Sushi Yama ',
      fromAccountId: CURRENT,
      categoryId: CATEGORY,
    });

    expect(result.error).toBeNull();
    expect(result.payload).toEqual({
      kind: 'EXPENSE',
      amount_minor: 2480,
      occurred_on: '2026-09-25',
      description: 'Sushi Yama',
      from_account_id: CURRENT,
      category_id: CATEGORY,
    });
  });

  it('rejects an invalid amount before anything else', () => {
    const result = validateForm({ ...emptyForm('EXPENSE', '2026-09-25'), amount: '0' });

    expect(result.payload).toBeNull();
    expect(result.error).toMatch(/amount/i);
  });

  it('requires the fields of the chosen type', () => {
    const base = { ...emptyForm('EXPENSE', '2026-09-25'), amount: '10' };

    expect(validateForm(base).error).toMatch(/category/i);
    expect(validateForm({ ...base, categoryId: CATEGORY }).error).toMatch(/account/i);
    expect(validateForm({ ...base, type: 'INVESTMENT', fromAccountId: CURRENT }).error).toMatch(
      /invested/i,
    );
    expect(validateForm({ ...base, type: 'REIMBURSEMENT', toAccountId: CURRENT }).error).toMatch(
      /expense/i,
    );
  });

  it('turns Save into a TRANSFER payload and rejects the same account twice', () => {
    const form = {
      ...emptyForm('SAVE', '2026-09-25'),
      amount: '500',
      fromAccountId: CURRENT,
      toAccountId: SAVINGS,
    };

    expect(validateForm(form).payload).toEqual({
      kind: 'TRANSFER',
      amount_minor: 50000,
      occurred_on: '2026-09-25',
      description: null,
      from_account_id: CURRENT,
      to_account_id: SAVINGS,
    });
    expect(validateForm({ ...form, toAccountId: CURRENT }).error).toMatch(/different/i);
  });

  it('prefills an edit form and recognises a saving', () => {
    const transaction: Transaction = {
      id: 't1',
      kind: 'TRANSFER',
      amount_minor: 50000,
      occurred_on: '2026-09-20',
      description: null,
      from_account_id: CURRENT,
      to_account_id: SAVINGS,
      category_id: null,
      investment_asset_id: null,
      reimburses_transaction_id: null,
      reimbursed_amount_minor: 0,
      created_at: '2026-09-20T10:00:00Z',
      updated_at: '2026-09-20T10:00:00Z',
    };

    const form = formFromTransaction(transaction, accounts);

    expect(form.type).toBe('SAVE');
    expect(form.amount).toBe('500.00');
    expect(form.toAccountId).toBe(SAVINGS);
  });

  it('never sends the kind in an update', () => {
    const { payload } = validateForm({
      ...emptyForm('INCOME', '2026-09-01'),
      amount: '3000',
      toAccountId: CURRENT,
      categoryId: CATEGORY,
    });

    expect(toUpdatePayload(payload!)).toEqual({
      amount_minor: 300000,
      occurred_on: '2026-09-01',
      description: null,
      to_account_id: CURRENT,
      category_id: CATEGORY,
    });
  });
});
