import {
  Account,
  Transaction,
  TransactionCreate,
  TransactionKind,
  TransactionUpdate,
} from '../../core/api/api.models';
import { minorToInput, parseAmountToMinor } from '../../shared/money';

/**
 * Pure logic of the Quick Add / edit form. "Save" is not a transaction
 * kind: it is a TRANSFER whose destination is a SAVINGS account, offered as
 * its own entry type so saving money is one tap away.
 */

export type EntryType = 'EXPENSE' | 'INCOME' | 'TRANSFER' | 'SAVE' | 'INVESTMENT' | 'REIMBURSEMENT';

export interface EntryTypeOption {
  type: EntryType;
  label: string;
  icon: string;
}

export const ENTRY_TYPES: EntryTypeOption[] = [
  { type: 'EXPENSE', label: 'Expense', icon: 'arrow-up-right' },
  { type: 'INCOME', label: 'Income', icon: 'arrow-down-left' },
  { type: 'TRANSFER', label: 'Transfer', icon: 'arrow-left-right' },
  { type: 'SAVE', label: 'Save', icon: 'piggy-bank' },
  { type: 'INVESTMENT', label: 'Invest', icon: 'chart-candlestick' },
  { type: 'REIMBURSEMENT', label: 'Refund', icon: 'undo-2' },
];

export interface FormState {
  type: EntryType;
  amount: string;
  date: string;
  description: string;
  fromAccountId: string | null;
  toAccountId: string | null;
  categoryId: string | null;
  investmentAssetId: string | null;
  reimbursesTransactionId: string | null;
}

export function kindOf(type: EntryType): TransactionKind {
  return type === 'SAVE' ? 'TRANSFER' : type;
}

export function emptyForm(type: EntryType, today: string): FormState {
  return {
    type,
    amount: '',
    date: today,
    description: '',
    fromAccountId: null,
    toAccountId: null,
    categoryId: null,
    investmentAssetId: null,
    reimbursesTransactionId: null,
  };
}

/** Form state for editing; a transfer into a savings account shows as "Save". */
export function formFromTransaction(
  transaction: Transaction,
  accountsById: Map<string, Account>,
): FormState {
  const destination = transaction.to_account_id
    ? accountsById.get(transaction.to_account_id)
    : undefined;
  const type: EntryType =
    transaction.kind === 'TRANSFER' && destination?.type === 'SAVINGS' ? 'SAVE' : transaction.kind;

  return {
    type,
    amount: minorToInput(transaction.amount_minor),
    date: transaction.occurred_on,
    description: transaction.description ?? '',
    fromAccountId: transaction.from_account_id,
    toAccountId: transaction.to_account_id,
    categoryId: transaction.category_id,
    investmentAssetId: transaction.investment_asset_id,
    reimbursesTransactionId: transaction.reimburses_transaction_id,
  };
}

export interface ValidationResult {
  payload: TransactionCreate | null;
  error: string | null;
}

/** Validate the form and build the API payload for its kind. */
export function validateForm(state: FormState): ValidationResult {
  const amount = parseAmountToMinor(state.amount);

  if (amount === null) {
    return { payload: null, error: 'Enter an amount greater than zero, with up to two decimals.' };
  }

  if (!/^\d{4}-\d{2}-\d{2}$/.test(state.date)) {
    return { payload: null, error: 'Choose a date.' };
  }

  const base = {
    amount_minor: amount,
    occurred_on: state.date,
    description: state.description.trim() || null,
  };

  switch (state.type) {
    case 'EXPENSE':
      if (!state.categoryId) return { payload: null, error: 'Choose a category.' };
      if (!state.fromAccountId)
        return { payload: null, error: 'Choose the account it was paid from.' };
      return {
        payload: {
          ...base,
          kind: 'EXPENSE',
          from_account_id: state.fromAccountId,
          category_id: state.categoryId,
        },
        error: null,
      };
    case 'INCOME':
      if (!state.categoryId) return { payload: null, error: 'Choose a category.' };
      if (!state.toAccountId)
        return { payload: null, error: 'Choose the account that received it.' };
      return {
        payload: {
          ...base,
          kind: 'INCOME',
          to_account_id: state.toAccountId,
          category_id: state.categoryId,
        },
        error: null,
      };
    case 'TRANSFER':
    case 'SAVE':
      if (!state.fromAccountId) return { payload: null, error: 'Choose the source account.' };
      if (!state.toAccountId) return { payload: null, error: 'Choose the destination account.' };
      if (state.fromAccountId === state.toAccountId) {
        return { payload: null, error: 'Source and destination must be different accounts.' };
      }
      return {
        payload: {
          ...base,
          kind: 'TRANSFER',
          from_account_id: state.fromAccountId,
          to_account_id: state.toAccountId,
        },
        error: null,
      };
    case 'INVESTMENT':
      if (!state.fromAccountId)
        return { payload: null, error: 'Choose the account the money left from.' };
      if (!state.investmentAssetId) return { payload: null, error: 'Choose what you invested in.' };
      return {
        payload: {
          ...base,
          kind: 'INVESTMENT',
          from_account_id: state.fromAccountId,
          investment_asset_id: state.investmentAssetId,
        },
        error: null,
      };
    case 'REIMBURSEMENT':
      if (!state.reimbursesTransactionId)
        return { payload: null, error: 'Choose the expense being refunded.' };
      if (!state.toAccountId)
        return { payload: null, error: 'Choose the account that received it.' };
      return {
        payload: {
          ...base,
          kind: 'REIMBURSEMENT',
          to_account_id: state.toAccountId,
          reimburses_transaction_id: state.reimbursesTransactionId,
        },
        error: null,
      };
  }
}

/** The same fields as a PATCH body (the kind is never sent). */
export function toUpdatePayload(payload: TransactionCreate): TransactionUpdate {
  const { kind: _kind, ...rest } = payload;
  return rest;
}
