import { httpResource } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { environment } from '../../../environments/environment';
import {
  CategoryBreakdown,
  CategoryKind,
  FinancialOverview,
  InvestmentSummary,
  MonthlyTrend,
  SavingsSummary,
} from '../../core/api/api.models';
import { RefreshService } from '../../core/refresh.service';

export interface Bounds {
  from: string;
  to: string;
}

/**
 * Report resources. Each factory returns an `httpResource` that follows
 * the period signal it is given and refetches after any mutation. Every
 * number comes from the API; nothing is computed here.
 */
@Injectable({ providedIn: 'root' })
export class ReportsService {
  private readonly refresh = inject(RefreshService);
  private readonly base = `${environment.apiBaseUrl}/reports`;

  overview(period: () => Bounds) {
    return httpResource<FinancialOverview>(() => this.request('overview', period()));
  }

  categories(period: () => Bounds, kind: CategoryKind) {
    return httpResource<CategoryBreakdown>(() => this.request('categories', period(), { kind }));
  }

  savings(period: () => Bounds) {
    return httpResource<SavingsSummary>(() => this.request('savings', period()));
  }

  investments(period: () => Bounds | null) {
    return httpResource<InvestmentSummary>(() => this.request('investments', period()));
  }

  monthlyTrend(months: number, until: () => string) {
    return httpResource<MonthlyTrend>(() => {
      this.refresh.version();
      return { url: `${this.base}/monthly-trend`, params: { months, until: until() } };
    });
  }

  private request(path: string, period: Bounds | null, extra: Record<string, string> = {}) {
    this.refresh.version();
    return {
      url: `${this.base}/${path}`,
      params: period ? { from: period.from, to: period.to, ...extra } : extra,
    };
  }
}
