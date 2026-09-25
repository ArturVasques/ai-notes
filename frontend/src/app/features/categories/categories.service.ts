import { HttpClient, httpResource } from '@angular/common/http';
import { computed, inject, Injectable } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../../environments/environment';
import { Category, CategoryCreate, CategoryUpdate } from '../../core/api/api.models';
import { RefreshService } from '../../core/refresh.service';

@Injectable({ providedIn: 'root' })
export class CategoriesService {
  private readonly http = inject(HttpClient);
  private readonly refresh = inject(RefreshService);
  private readonly base = `${environment.apiBaseUrl}/categories`;

  readonly all = httpResource<Category[]>(
    () => {
      this.refresh.version();
      return { url: this.base, params: { include_archived: true } };
    },
    { defaultValue: [] },
  );

  readonly active = computed(() => this.all.value().filter((category) => !category.archived_at));
  readonly activeExpense = computed(() => this.active().filter((c) => c.kind === 'EXPENSE'));
  readonly activeIncome = computed(() => this.active().filter((c) => c.kind === 'INCOME'));
  readonly byId = computed(() => new Map(this.all.value().map((c) => [c.id, c])));

  async create(body: CategoryCreate): Promise<Category> {
    const category = await firstValueFrom(this.http.post<Category>(this.base, body));
    this.refresh.bump();
    return category;
  }

  async update(id: string, body: CategoryUpdate): Promise<Category> {
    const category = await firstValueFrom(this.http.patch<Category>(`${this.base}/${id}`, body));
    this.refresh.bump();
    return category;
  }
}
