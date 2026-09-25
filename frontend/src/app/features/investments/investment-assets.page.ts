import { Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { InvestmentAsset, InvestmentAssetType } from '../../core/api/api.models';
import { errorMessage } from '../../core/api/api-error';
import { ToastService } from '../../core/toast.service';
import { IconComponent } from '../../shared/icon.component';
import { SheetComponent } from '../../shared/sheet.component';
import { InvestmentAssetsService } from './investment-assets.service';

const ASSET_TYPES: { type: InvestmentAssetType; label: string }[] = [
  { type: 'ETF', label: 'ETF' },
  { type: 'STOCK', label: 'Stock' },
  { type: 'FUND', label: 'Fund' },
  { type: 'BOND', label: 'Bond' },
  { type: 'CRYPTO', label: 'Crypto' },
  { type: 'OTHER', label: 'Other' },
];

interface AssetForm {
  name: string;
  symbol: string;
  type: InvestmentAssetType;
}

@Component({
  selector: 'app-investment-assets-page',
  imports: [RouterLink, IconComponent, SheetComponent],
  template: `
    <div class="page">
      <div class="page-head">
        <div class="page-head__titles">
          <a class="back" routerLink="/settings"
            ><app-icon name="chevron-left" [size]="16" /> Settings</a
          >
          <h1>Investment assets</h1>
        </div>
        <div class="page-head__tools">
          <button type="button" class="btn btn--small btn--primary" (click)="openNew()">
            <app-icon name="plus" [size]="14" /> Add
          </button>
        </div>
      </div>

      @if (visible().length === 0) {
        <div class="empty">
          <p class="empty__title">No investment assets yet</p>
          <p>Add an ETF, a stock or a fund to record where your money is invested.</p>
        </div>
      } @else {
        <div class="group fade-in">
          @for (asset of visible(); track asset.id) {
            <button type="button" class="row-item" (click)="openEdit(asset)">
              <span class="row-item__icon row-item__icon--inv">
                <app-icon name="chart-candlestick" [size]="17" [strokeWidth]="1.75" />
              </span>
              <span class="row-item__main">
                <span class="row-item__title">
                  {{ asset.name }}
                  @if (asset.archived_at) {
                    <span class="badge">Archived</span>
                  }
                </span>
                <span class="row-item__sub"
                  >{{ asset.symbol ? asset.symbol + ' · ' : '' }}{{ typeLabel(asset.type) }}</span
                >
              </span>
              <app-icon class="row-item__chevron" name="chevron-right" [size]="16" />
            </button>
          }
        </div>
      }
      <button
        type="button"
        class="btn btn--quiet btn--small"
        (click)="showArchived.set(!showArchived())"
      >
        {{ showArchived() ? 'Hide archived' : 'Show archived' }}
      </button>

      <app-sheet [(open)]="sheetOpen" [title]="editing() ? 'Edit asset' : 'New asset'">
        <form class="sheet-form" (submit)="save($event)">
          <div class="group">
            <label class="form-row form-row--static">
              <span class="form-row__label">Name</span>
              <input
                #name
                class="form-row__input"
                type="text"
                maxlength="100"
                placeholder="S&P 500"
                [value]="form().name"
                (input)="patch({ name: name.value })"
              />
            </label>
            <label class="form-row form-row--static">
              <span class="form-row__label">Symbol</span>
              <input
                #symbol
                class="form-row__input"
                type="text"
                maxlength="20"
                placeholder="Optional"
                [value]="form().symbol"
                (input)="patch({ symbol: symbol.value })"
              />
            </label>
            <button type="button" class="form-row" (click)="typeOpen.set(!typeOpen())">
              <span class="form-row__label">Type</span>
              <span class="form-row__value">{{ typeLabel(form().type) }}</span>
              <app-icon
                class="chevron row-item__chevron"
                [class.chevron--open]="typeOpen()"
                name="chevron-right"
                [size]="16"
              />
            </button>
            @if (typeOpen()) {
              <div class="form-expand">
                <div class="chips">
                  @for (option of types; track option.type) {
                    <button
                      type="button"
                      class="chip"
                      [class.chip--on]="form().type === option.type"
                      (click)="patch({ type: option.type }); typeOpen.set(false)"
                    >
                      {{ option.label }}
                    </button>
                  }
                </div>
              </div>
            }
          </div>
          @if (error()) {
            <p class="form-error error-in" role="alert">{{ error() }}</p>
          }
          <div class="sheet-form__actions">
            @if (editing(); as asset) {
              <button
                type="button"
                class="btn btn--quiet"
                [disabled]="busy()"
                (click)="toggleArchive(asset)"
              >
                {{ asset.archived_at ? 'Restore' : 'Archive' }}
              </button>
            }
            <button type="submit" class="btn btn--primary grow" [disabled]="busy()">
              {{ editing() ? 'Save changes' : 'Add asset' }}
            </button>
          </div>
        </form>
      </app-sheet>
    </div>
  `,
})
export class InvestmentAssetsPage {
  private readonly assets = inject(InvestmentAssetsService);
  private readonly toasts = inject(ToastService);

  readonly types = ASSET_TYPES;
  readonly showArchived = signal(false);
  readonly visible = computed(() =>
    this.assets.all.value().filter((asset) => this.showArchived() || !asset.archived_at),
  );

  readonly sheetOpen = signal(false);
  readonly typeOpen = signal(false);
  readonly editing = signal<InvestmentAsset | null>(null);
  readonly form = signal<AssetForm>({ name: '', symbol: '', type: 'ETF' });
  readonly error = signal<string | null>(null);
  readonly busy = signal(false);

  typeLabel(type: InvestmentAssetType): string {
    return ASSET_TYPES.find((option) => option.type === type)?.label ?? type;
  }

  openNew(): void {
    this.editing.set(null);
    this.form.set({ name: '', symbol: '', type: 'ETF' });
    this.error.set(null);
    this.typeOpen.set(false);
    this.sheetOpen.set(true);
  }

  openEdit(asset: InvestmentAsset): void {
    this.editing.set(asset);
    this.form.set({ name: asset.name, symbol: asset.symbol ?? '', type: asset.type });
    this.error.set(null);
    this.typeOpen.set(false);
    this.sheetOpen.set(true);
  }

  patch(changes: Partial<AssetForm>): void {
    this.form.update((state) => ({ ...state, ...changes }));
    this.error.set(null);
  }

  async save(event: Event): Promise<void> {
    event.preventDefault();

    const state = this.form();
    const name = state.name.trim();

    if (!name) {
      this.error.set('Enter a name.');
      return;
    }

    this.busy.set(true);

    try {
      const editing = this.editing();
      const body = { name, symbol: state.symbol.trim() || null, type: state.type };

      if (editing) {
        await this.assets.update(editing.id, body);
      } else {
        await this.assets.create(body);
      }

      this.sheetOpen.set(false);
      this.toasts.show(editing ? 'Asset updated' : 'Asset added');
    } catch (failure) {
      this.error.set(errorMessage(failure));
    } finally {
      this.busy.set(false);
    }
  }

  async toggleArchive(asset: InvestmentAsset): Promise<void> {
    this.busy.set(true);

    try {
      await this.assets.update(asset.id, { archived: !asset.archived_at });
      this.sheetOpen.set(false);
      this.toasts.show(asset.archived_at ? 'Asset restored' : 'Asset archived', 'neutral');
    } catch (failure) {
      this.error.set(errorMessage(failure));
    } finally {
      this.busy.set(false);
    }
  }
}
