import { Component, computed, inject, input } from '@angular/core';
import { DomSanitizer } from '@angular/platform-browser';
import { iconSvg, resolveIcon } from './icons';

/**
 * Renders an allowlisted Lucide icon inline. The markup is generated from
 * the icon table in icons.ts, never from user input, so bypassing the
 * sanitizer here is safe.
 */
@Component({
  selector: 'app-icon',
  template: '<span class="icon" [innerHTML]="svg()"></span>',
  styles: `
    :host {
      display: inline-flex;
      line-height: 0;
    }
  `,
})
export class IconComponent {
  private readonly sanitizer = inject(DomSanitizer);

  readonly name = input.required<string>();
  readonly size = input(20);
  readonly strokeWidth = input(2);

  readonly svg = computed(() =>
    this.sanitizer.bypassSecurityTrustHtml(
      iconSvg(resolveIcon(this.name()), this.size(), this.strokeWidth()),
    ),
  );
}
