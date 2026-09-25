import { Transaction } from '../../core/api/api.models';
import { groupByDay } from './transaction-grouping';

function transaction(id: string, occurredOn: string): Transaction {
  return {
    id,
    kind: 'EXPENSE',
    amount_minor: 100,
    occurred_on: occurredOn,
    description: null,
    from_account_id: 'a',
    to_account_id: null,
    category_id: 'c',
    investment_asset_id: null,
    reimburses_transaction_id: null,
    reimbursed_amount_minor: 0,
    created_at: `${occurredOn}T10:00:00Z`,
    updated_at: `${occurredOn}T10:00:00Z`,
  };
}

describe('groupByDay', () => {
  it('groups consecutive transactions of the same day with readable labels', () => {
    const now = new Date(2026, 8, 25);
    const groups = groupByDay(
      [
        transaction('1', '2026-09-25'),
        transaction('2', '2026-09-25'),
        transaction('3', '2026-09-24'),
        transaction('4', '2026-09-01'),
      ],
      now,
    );

    expect(groups.map((group) => [group.label, group.items.length])).toEqual([
      ['Today', 2],
      ['Yesterday', 1],
      ['Tue 1 Sept', 1],
    ]);
  });

  it('returns nothing for an empty list', () => {
    expect(groupByDay([])).toEqual([]);
  });
});
