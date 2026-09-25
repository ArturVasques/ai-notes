import { provideHttpClient, withInterceptors } from '@angular/common/http';
import {
  ApplicationConfig,
  inject,
  provideAppInitializer,
  provideBrowserGlobalErrorListeners,
} from '@angular/core';
import {
  ActivatedRouteSnapshot,
  provideRouter,
  withComponentInputBinding,
  withInMemoryScrolling,
  withViewTransitions,
} from '@angular/router';
import { routes } from './app.routes';
import { provideMsal } from './core/auth/auth.config';
import { authInterceptor } from './core/auth/auth.interceptor';
import { isTabUrl } from './core/layout/swipe-navigation';
import { ThemeService } from './core/theme.service';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    // Applies the saved day/night mode before the first paint.
    provideAppInitializer(() => {
      inject(ThemeService);
    }),
    provideRouter(
      routes,
      withComponentInputBinding(),
      withInMemoryScrolling({ scrollPositionRestoration: 'top' }),
      withViewTransitions({
        skipInitialTransition: true,
        // Tab changes are animated by the pager itself; only nested pages
        // (Settings sub-pages) use the document crossfade.
        onViewTransitionCreated: ({ transition, from, to }) => {
          if (isTabUrl(snapshotUrl(from)) && isTabUrl(snapshotUrl(to))) {
            transition.skipTransition();
          }
        },
      }),
    ),
    provideMsal(),
    provideHttpClient(withInterceptors([authInterceptor])),
  ],
};

function snapshotUrl(snapshot: ActivatedRouteSnapshot): string {
  let deepest = snapshot;

  while (deepest.firstChild) {
    deepest = deepest.firstChild;
  }

  return (
    '/' +
    deepest.pathFromRoot.flatMap((route) => route.url.map((segment) => segment.path)).join('/')
  );
}
