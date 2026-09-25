/**
 * TypeScript view of the API contracts (backend/app/schemas). Every amount
 * is an integer number of minor units (cents); dates are `YYYY-MM-DD`.
 */

export type AccountType = 'CHECKING' | 'SAVINGS' | 'CASH' | 'BENEFITS' | 'BROKERAGE';

export interface Account {
  id: string;
  name: string;
  type: AccountType;
  description: string | null;
  currency: string;
  opening_balance_minor: number;
  archived_at: string | null;
  created_at: string;
}

export interface AccountCreate {
  name: string;
  type: AccountType;
  description?: string | null;
  opening_balance_minor?: number;
}

export interface AccountUpdate {
  name?: string;
  type?: AccountType;
  description?: string | null;
  opening_balance_minor?: number;
  archived?: boolean;
}

export type CategoryKind = 'EXPENSE' | 'INCOME';

export interface Category {
  id: string;
  name: string;
  kind: CategoryKind;
  icon: string;
  archived_at: string | null;
  created_at: string;
}

export interface CategoryCreate {
  name: string;
  kind: CategoryKind;
  icon: string;
}

export interface CategoryUpdate {
  name?: string;
  icon?: string;
  archived?: boolean;
}

export type InvestmentAssetType = 'ETF' | 'STOCK' | 'FUND' | 'BOND' | 'CRYPTO' | 'OTHER';

export interface InvestmentAsset {
  id: string;
  name: string;
  symbol: string | null;
  type: InvestmentAssetType;
  archived_at: string | null;
  created_at: string;
}

export interface InvestmentAssetCreate {
  name: string;
  symbol?: string | null;
  type: InvestmentAssetType;
}

export interface InvestmentAssetUpdate {
  name?: string;
  symbol?: string | null;
  type?: InvestmentAssetType;
  archived?: boolean;
}

export type TransactionKind = 'INCOME' | 'EXPENSE' | 'TRANSFER' | 'INVESTMENT' | 'REIMBURSEMENT';

export interface Transaction {
  id: string;
  kind: TransactionKind;
  amount_minor: number;
  occurred_on: string;
  description: string | null;
  from_account_id: string | null;
  to_account_id: string | null;
  category_id: string | null;
  investment_asset_id: string | null;
  reimburses_transaction_id: string | null;
  reimbursed_amount_minor: number;
  created_at: string;
  updated_at: string;
}

interface TransactionBase {
  amount_minor: number;
  occurred_on: string;
  description?: string | null;
}

export interface ExpenseCreate extends TransactionBase {
  kind: 'EXPENSE';
  from_account_id: string;
  category_id: string;
}

export interface IncomeCreate extends TransactionBase {
  kind: 'INCOME';
  to_account_id: string;
  category_id: string;
}

export interface TransferCreate extends TransactionBase {
  kind: 'TRANSFER';
  from_account_id: string;
  to_account_id: string;
}

export interface InvestmentCreate extends TransactionBase {
  kind: 'INVESTMENT';
  from_account_id: string;
  investment_asset_id: string;
}

export interface ReimbursementCreate extends TransactionBase {
  kind: 'REIMBURSEMENT';
  to_account_id: string;
  reimburses_transaction_id: string;
}

export type TransactionCreate =
  ExpenseCreate | IncomeCreate | TransferCreate | InvestmentCreate | ReimbursementCreate;

export type TransactionUpdate = Partial<Omit<TransactionCreate, 'kind'>>;

export interface TransactionFilters {
  from?: string;
  to?: string;
  kind?: TransactionKind;
  category_id?: string;
  account_id?: string;
  investment_asset_id?: string;
}

export interface TransactionPage {
  items: Transaction[];
  next_cursor: string | null;
}

export interface SavingsAllocation {
  savings_accounts_minor: number;
  investments_minor: number;
  retained_cash_minor: number;
}

export interface FinancialOverview {
  date_from: string;
  date_to: string;
  income_minor: number;
  gross_expenses_minor: number;
  reimbursements_attributed_minor: number;
  effective_expenses_minor: number;
  net_savings_minor: number;
  savings_rate: number | null;
  allocation: SavingsAllocation;
  reimbursements_received_minor: number;
  net_cash_flow_minor: number;
  transfers_minor: number;
}

export interface CategoryBreakdownItem {
  category_id: string;
  name: string;
  icon: string;
  kind: CategoryKind;
  archived: boolean;
  gross_minor: number;
  reimbursed_minor: number;
  effective_minor: number;
  transaction_count: number;
}

export interface CategoryBreakdown {
  date_from: string;
  date_to: string;
  kind: CategoryKind;
  total_minor: number;
  items: CategoryBreakdownItem[];
}

export interface SavingsAccountMovement {
  account_id: string;
  name: string;
  archived: boolean;
  inflows_minor: number;
  outflows_minor: number;
  net_minor: number;
}

export interface SavingsSummary {
  date_from: string;
  date_to: string;
  income_minor: number;
  effective_expenses_minor: number;
  net_savings_minor: number;
  savings_rate: number | null;
  allocation: SavingsAllocation;
  savings_accounts: SavingsAccountMovement[];
}

export interface InvestmentByAsset {
  investment_asset_id: string;
  name: string;
  symbol: string | null;
  type: InvestmentAssetType;
  archived: boolean;
  invested_minor: number;
  transaction_count: number;
}

export interface InvestmentBySource {
  account_id: string;
  name: string;
  invested_minor: number;
}

export interface InvestmentSummary {
  date_from: string | null;
  date_to: string | null;
  total_invested_minor: number;
  by_asset: InvestmentByAsset[];
  by_source_account: InvestmentBySource[];
}

export interface MonthlyPoint {
  month: string;
  income_minor: number;
  gross_expenses_minor: number;
  effective_expenses_minor: number;
  net_savings_minor: number;
  savings_rate: number | null;
  savings_accounts_minor: number;
  invested_minor: number;
  retained_cash_minor: number;
  net_cash_flow_minor: number;
}

export interface MonthlyTrend {
  months: MonthlyPoint[];
}

export interface AccountBalance {
  account: Account;
  balance_minor: number;
}

export interface AccountBalances {
  as_of: string | null;
  items: AccountBalance[];
  total_minor: number;
}

export interface UserProfile {
  id: string;
  name: string;
  email: string | null;
}

export interface ApiError {
  code: string;
  message: string;
}
