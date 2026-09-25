import { HttpClient, httpResource } from '@angular/common/http';
import { computed, inject, Injectable } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../../environments/environment';
import { Account, AccountBalances, AccountCreate, AccountUpdate } from '../../core/api/api.models';
import { RefreshService } from '../../core/refresh.service';

@Injectable({ providedIn: 'root' })
export class AccountsService {
  private readonly http = inject(HttpClient);
  private readonly refresh = inject(RefreshService);
  private readonly base = `${environment.apiBaseUrl}/accounts`;

  /** Every account, archived included; refetched after any mutation. */
  readonly all = httpResource<Account[]>(
    () => {
      this.refresh.version();
      return { url: this.base, params: { include_archived: true } };
    },
    { defaultValue: [] },
  );

  readonly active = computed(() => this.all.value().filter((account) => !account.archived_at));
  readonly byId = computed(() => new Map(this.all.value().map((account) => [account.id, account])));

  /** Balances as of today; follows the `includeArchived` signal it is given. */
  balances(includeArchived: () => boolean) {
    return httpResource<AccountBalances>(() => {
      this.refresh.version();
      return { url: `${this.base}/balances`, params: { include_archived: includeArchived() } };
    });
  }

  async create(body: AccountCreate): Promise<Account> {
    const account = await firstValueFrom(this.http.post<Account>(this.base, body));
    this.refresh.bump();
    return account;
  }

  async update(id: string, body: AccountUpdate): Promise<Account> {
    const account = await firstValueFrom(this.http.patch<Account>(`${this.base}/${id}`, body));
    this.refresh.bump();
    return account;
  }
}
