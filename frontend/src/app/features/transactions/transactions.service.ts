import { HttpClient, httpResource } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../../environments/environment';
import {
  Transaction,
  TransactionCreate,
  TransactionFilters,
  TransactionPage,
  TransactionUpdate,
} from '../../core/api/api.models';
import { RefreshService } from '../../core/refresh.service';

@Injectable({ providedIn: 'root' })
export class TransactionsService {
  private readonly http = inject(HttpClient);
  private readonly refresh = inject(RefreshService);
  private readonly base = `${environment.apiBaseUrl}/transactions`;

  /** First page of history for reactive filters; refetched after mutations. */
  page(filters: () => TransactionFilters, limit: () => number) {
    return httpResource<TransactionPage>(() => {
      this.refresh.version();
      return { url: this.base, params: { ...definedOnly(filters()), limit: limit() } };
    });
  }

  /** Following pages, appended by the caller. */
  loadMore(filters: TransactionFilters, cursor: string, limit: number): Promise<TransactionPage> {
    return firstValueFrom(
      this.http.get<TransactionPage>(this.base, {
        params: { ...definedOnly(filters), limit, cursor },
      }),
    );
  }

  async create(body: TransactionCreate): Promise<Transaction> {
    const transaction = await firstValueFrom(this.http.post<Transaction>(this.base, body));
    this.refresh.bump();
    return transaction;
  }

  async update(id: string, body: TransactionUpdate): Promise<Transaction> {
    const transaction = await firstValueFrom(
      this.http.patch<Transaction>(`${this.base}/${id}`, body),
    );
    this.refresh.bump();
    return transaction;
  }

  async delete(id: string): Promise<void> {
    await firstValueFrom(this.http.delete<void>(`${this.base}/${id}`));
    this.refresh.bump();
  }
}

function definedOnly(filters: TransactionFilters): Record<string, string> {
  return Object.fromEntries(
    Object.entries(filters).filter((entry): entry is [string, string] => entry[1] !== undefined),
  );
}
