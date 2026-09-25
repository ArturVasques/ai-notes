import { HttpClient, httpResource } from '@angular/common/http';
import { computed, inject, Injectable } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../../environments/environment';
import {
  InvestmentAsset,
  InvestmentAssetCreate,
  InvestmentAssetUpdate,
} from '../../core/api/api.models';
import { RefreshService } from '../../core/refresh.service';

@Injectable({ providedIn: 'root' })
export class InvestmentAssetsService {
  private readonly http = inject(HttpClient);
  private readonly refresh = inject(RefreshService);
  private readonly base = `${environment.apiBaseUrl}/investment-assets`;

  readonly all = httpResource<InvestmentAsset[]>(
    () => {
      this.refresh.version();
      return { url: this.base, params: { include_archived: true } };
    },
    { defaultValue: [] },
  );

  readonly active = computed(() => this.all.value().filter((asset) => !asset.archived_at));
  readonly byId = computed(() => new Map(this.all.value().map((asset) => [asset.id, asset])));

  async create(body: InvestmentAssetCreate): Promise<InvestmentAsset> {
    const asset = await firstValueFrom(this.http.post<InvestmentAsset>(this.base, body));
    this.refresh.bump();
    return asset;
  }

  async update(id: string, body: InvestmentAssetUpdate): Promise<InvestmentAsset> {
    const asset = await firstValueFrom(
      this.http.patch<InvestmentAsset>(`${this.base}/${id}`, body),
    );
    this.refresh.bump();
    return asset;
  }
}
