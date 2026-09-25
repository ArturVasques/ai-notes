import { Pipe, PipeTransform } from '@angular/core';
import { formatMinor } from './money';

/** `{{ 2480 | money }}` → "€24.80"; `{{ 2480 | money:'signed' }}` → "+€24.80". */
@Pipe({ name: 'money' })
export class MoneyPipe implements PipeTransform {
  transform(minor: number | null | undefined, mode?: 'signed'): string {
    if (minor === null || minor === undefined) {
      return '—';
    }

    return formatMinor(minor, { signed: mode === 'signed' });
  }
}
