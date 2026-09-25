import { Transaction } from '../../core/api/api.models';
import { formatDayLabel } from '../../shared/dates';

export interface DayGroup {
  date: string;
  label: string;
  items: Transaction[];
}

/** Group an already newest-first list into day sections for the history. */
export function groupByDay(transactions: Transaction[], now: Date = new Date()): DayGroup[] {
  const groups: DayGroup[] = [];

  for (const transaction of transactions) {
    const last = groups[groups.length - 1];

    if (last && last.date === transaction.occurred_on) {
      last.items.push(transaction);
    } else {
      groups.push({
        date: transaction.occurred_on,
        label: formatDayLabel(transaction.occurred_on, now),
        items: [transaction],
      });
    }
  }

  return groups;
}
