import { computed, effect, Injectable, signal } from '@angular/core';

export type ThemeMode = 'system' | 'light' | 'dark';

const STORAGE_KEY = 'pf.theme';
const THEME_COLORS = { light: '#f5f5f7', dark: '#000000' } as const;

/**
 * Day / night appearance. "system" follows the device; "light" and "dark"
 * force a mode through `<html data-theme>`, which the design tokens read.
 * The choice is remembered per browser (a per-device convenience only).
 */
@Injectable({ providedIn: 'root' })
export class ThemeService {
  private readonly systemDark = signal(matchesDark());

  readonly mode = signal<ThemeMode>(readStoredMode());

  readonly effective = computed<'light' | 'dark'>(() => {
    const mode = this.mode();
    return mode === 'system' ? (this.systemDark() ? 'dark' : 'light') : mode;
  });

  constructor() {
    const media = window.matchMedia?.('(prefers-color-scheme: dark)');
    media?.addEventListener?.('change', (event) => this.systemDark.set(event.matches));

    effect(() => {
      const root = document.documentElement;
      const mode = this.mode();
      const effective = this.effective();

      if (mode === 'system') {
        delete root.dataset['theme'];
      } else {
        root.dataset['theme'] = mode;
      }

      root.style.colorScheme = effective;

      for (const meta of document.querySelectorAll<HTMLMetaElement>('meta[name="theme-color"]')) {
        meta.content = THEME_COLORS[effective];
      }
    });
  }

  setMode(mode: ThemeMode): void {
    this.mode.set(mode);

    try {
      localStorage.setItem(STORAGE_KEY, mode);
    } catch {
      // Storage may be unavailable (private mode); the choice just does not persist.
    }
  }
}

function readStoredMode(): ThemeMode {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored === 'light' || stored === 'dark' ? stored : 'system';
  } catch {
    return 'system';
  }
}

function matchesDark(): boolean {
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false;
}
