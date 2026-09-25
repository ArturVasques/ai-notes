import { Component, effect, ElementRef, input, model, signal, viewChild } from '@angular/core';
import { IconComponent } from './icon.component';

/**
 * Bottom sheet on phones, centred panel on larger screens, built on the
 * native <dialog> element (modal focus handling and Escape for free) with a
 * glass surface. Opening and closing are animated; the dialog only closes
 * once the exit animation has finished.
 *
 * Usage: `<app-sheet [(open)]="isOpen" title="Add">…</app-sheet>`.
 */
@Component({
  selector: 'app-sheet',
  imports: [IconComponent],
  template: `
    <dialog
      #dialog
      class="sheet"
      [class.sheet--closing]="closing()"
      (cancel)="onCancel($event)"
      (click)="onBackdropClick($event)"
    >
      <div
        class="sheet__panel glass"
        [class.sheet__panel--closing]="closing()"
        (click)="$event.stopPropagation()"
        (animationend)="onAnimationEnd()"
      >
        <div class="sheet__grip" aria-hidden="true"></div>
        <header class="sheet__header">
          <ng-content select="[sheet-leading]" />
          <h2 class="sheet__title">{{ title() }}</h2>
          <button type="button" class="icon-button" aria-label="Close" (click)="close()">
            <app-icon name="x" [size]="18" />
          </button>
        </header>
        <div class="sheet__body">
          @if (mounted()) {
            <ng-content />
          }
        </div>
      </div>
    </dialog>
  `,
})
export class SheetComponent {
  readonly open = model(false);
  readonly title = input('');

  /** Content stays mounted while the exit animation plays. */
  readonly mounted = signal(false);
  readonly closing = signal(false);

  private readonly dialog = viewChild.required<ElementRef<HTMLDialogElement>>('dialog');

  constructor() {
    effect(() => {
      const element = this.dialog().nativeElement;

      if (this.open()) {
        this.closing.set(false);
        this.mounted.set(true);

        if (!element.open) {
          element.showModal();
        }
      } else if (element.open && !this.closing()) {
        this.closing.set(true);
      }
    });
  }

  close(): void {
    this.open.set(false);
  }

  onCancel(event: Event): void {
    event.preventDefault();
    this.close();
  }

  onBackdropClick(event: MouseEvent): void {
    if (event.target === this.dialog().nativeElement) {
      this.close();
    }
  }

  onAnimationEnd(): void {
    if (!this.closing()) {
      return;
    }

    const element = this.dialog().nativeElement;

    if (element.open) {
      element.close();
    }

    this.closing.set(false);
    this.mounted.set(false);
  }
}
