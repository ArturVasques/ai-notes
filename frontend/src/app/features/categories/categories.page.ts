import { Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Category, CategoryKind } from '../../core/api/api.models';
import { errorMessage } from '../../core/api/api-error';
import { ToastService } from '../../core/toast.service';
import { IconComponent } from '../../shared/icon.component';
import { CATEGORY_ICON_KEYS } from '../../shared/icons';
import { SheetComponent } from '../../shared/sheet.component';
import { CategoriesService } from './categories.service';

interface CategoryForm {
  name: string;
  kind: CategoryKind;
  icon: string;
}

@Component({
  selector: 'app-categories-page',
  imports: [RouterLink, IconComponent, SheetComponent],
  template: `
    <div class="page">
      <div class="page-head">
        <div class="page-head__titles">
          <a class="back" routerLink="/settings"
            ><app-icon name="chevron-left" [size]="16" /> Settings</a
          >
          <h1>Categories</h1>
        </div>
        <div class="page-head__tools">
          <button type="button" class="btn btn--small btn--primary" (click)="openNew()">
            <app-icon name="plus" [size]="14" /> Add
          </button>
        </div>
      </div>

      <div class="segmented" role="tablist">
        <button
          type="button"
          role="tab"
          class="segmented__option"
          [class.segmented__option--active]="kind() === 'EXPENSE'"
          [attr.aria-selected]="kind() === 'EXPENSE'"
          (click)="kind.set('EXPENSE')"
        >
          Expenses
        </button>
        <button
          type="button"
          role="tab"
          class="segmented__option"
          [class.segmented__option--active]="kind() === 'INCOME'"
          [attr.aria-selected]="kind() === 'INCOME'"
          (click)="kind.set('INCOME')"
        >
          Income
        </button>
      </div>

      @for (key of [kind()]; track key) {
        <div class="stack fade-in">
          @if (visible().length === 0) {
            <div class="empty">
              <p class="empty__title">
                No {{ kind() === 'EXPENSE' ? 'expense' : 'income' }} categories
              </p>
            </div>
          } @else {
            <div class="group">
              @for (category of visible(); track category.id) {
                <button type="button" class="row-item" (click)="openEdit(category)">
                  <span class="row-item__icon">
                    <app-icon [name]="category.icon" [size]="17" [strokeWidth]="1.75" />
                  </span>
                  <span class="row-item__main">
                    <span class="row-item__title">
                      {{ category.name }}
                      @if (category.archived_at) {
                        <span class="badge">Archived</span>
                      }
                    </span>
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
        </div>
      }

      <app-sheet [(open)]="sheetOpen" [title]="editing() ? 'Edit category' : 'New category'">
        <form class="sheet-form" (submit)="save($event)">
          <div class="group">
            <label class="form-row form-row--static">
              <span class="form-row__label">Name</span>
              <input
                #name
                class="form-row__input"
                type="text"
                maxlength="100"
                placeholder="Groceries"
                [value]="form().name"
                (input)="patch({ name: name.value })"
              />
            </label>
            @if (!editing()) {
              <div class="form-row form-row--static">
                <span class="form-row__label">Kind</span>
                <div class="chips" style="justify-content: flex-end; flex: 1">
                  <button
                    type="button"
                    class="chip"
                    [class.chip--on]="form().kind === 'EXPENSE'"
                    (click)="patch({ kind: 'EXPENSE' })"
                  >
                    Expense
                  </button>
                  <button
                    type="button"
                    class="chip"
                    [class.chip--on]="form().kind === 'INCOME'"
                    (click)="patch({ kind: 'INCOME' })"
                  >
                    Income
                  </button>
                </div>
              </div>
            }
          </div>
          <div class="stack" style="gap: var(--s-2)">
            <span class="eyebrow">Icon</span>
            <div class="icon-grid icon-grid--dense">
              @for (icon of iconKeys; track icon) {
                <button
                  type="button"
                  class="icon-tile"
                  [class.icon-tile--on]="form().icon === icon"
                  [attr.aria-label]="icon"
                  (click)="patch({ icon })"
                >
                  <app-icon [name]="icon" [size]="20" [strokeWidth]="1.75" />
                </button>
              }
            </div>
          </div>
          @if (error()) {
            <p class="form-error error-in" role="alert">{{ error() }}</p>
          }
          <div class="sheet-form__actions">
            @if (editing(); as category) {
              <button
                type="button"
                class="btn btn--quiet"
                [disabled]="busy()"
                (click)="toggleArchive(category)"
              >
                {{ category.archived_at ? 'Restore' : 'Archive' }}
              </button>
            }
            <button type="submit" class="btn btn--primary grow" [disabled]="busy()">
              {{ editing() ? 'Save changes' : 'Add category' }}
            </button>
          </div>
        </form>
      </app-sheet>
    </div>
  `,
})
export class CategoriesPage {
  private readonly categories = inject(CategoriesService);
  private readonly toasts = inject(ToastService);

  readonly iconKeys = CATEGORY_ICON_KEYS;
  readonly kind = signal<CategoryKind>('EXPENSE');
  readonly showArchived = signal(false);

  readonly visible = computed(() =>
    this.categories.all
      .value()
      .filter((category) => category.kind === this.kind())
      .filter((category) => this.showArchived() || !category.archived_at),
  );

  readonly sheetOpen = signal(false);
  readonly editing = signal<Category | null>(null);
  readonly form = signal<CategoryForm>({ name: '', kind: 'EXPENSE', icon: 'tag' });
  readonly error = signal<string | null>(null);
  readonly busy = signal(false);

  openNew(): void {
    this.editing.set(null);
    this.form.set({ name: '', kind: this.kind(), icon: 'tag' });
    this.error.set(null);
    this.sheetOpen.set(true);
  }

  openEdit(category: Category): void {
    this.editing.set(category);
    this.form.set({ name: category.name, kind: category.kind, icon: category.icon });
    this.error.set(null);
    this.sheetOpen.set(true);
  }

  patch(changes: Partial<CategoryForm>): void {
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

      if (editing) {
        await this.categories.update(editing.id, { name, icon: state.icon });
      } else {
        await this.categories.create({ name, kind: state.kind, icon: state.icon });
        this.kind.set(state.kind);
      }

      this.sheetOpen.set(false);
      this.toasts.show(editing ? 'Category updated' : 'Category added');
    } catch (failure) {
      this.error.set(errorMessage(failure));
    } finally {
      this.busy.set(false);
    }
  }

  async toggleArchive(category: Category): Promise<void> {
    this.busy.set(true);

    try {
      await this.categories.update(category.id, { archived: !category.archived_at });
      this.sheetOpen.set(false);
      this.toasts.show(category.archived_at ? 'Category restored' : 'Category archived', 'neutral');
    } catch (failure) {
      this.error.set(errorMessage(failure));
    } finally {
      this.busy.set(false);
    }
  }
}
