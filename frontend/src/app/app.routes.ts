import { Routes } from '@angular/router';
import { anonymousGuard, authGuard } from './core/auth/auth.guard';

/**
 * The four top-level tabs are rendered by the shell's swipeable pager, so
 * their routes carry no component: they only select the tab. Nested pages
 * render through the shell's outlet on top of the pager.
 */
export const routes: Routes = [
  {
    path: 'login',
    canActivate: [anonymousGuard],
    loadComponent: () => import('./core/auth/login.page').then((m) => m.LoginPage),
  },
  {
    path: '',
    canActivate: [authGuard],
    loadComponent: () => import('./core/layout/shell.component').then((m) => m.ShellComponent),
    children: [
      { path: '', pathMatch: 'full', children: [] },
      { path: 'transactions', pathMatch: 'full', children: [] },
      { path: 'insights', pathMatch: 'full', children: [] },
      { path: 'settings', pathMatch: 'full', children: [] },
      {
        path: 'settings/accounts',
        loadComponent: () =>
          import('./features/accounts/accounts.page').then((m) => m.AccountsPage),
      },
      {
        path: 'settings/categories',
        loadComponent: () =>
          import('./features/categories/categories.page').then((m) => m.CategoriesPage),
      },
      {
        path: 'settings/investment-assets',
        loadComponent: () =>
          import('./features/investments/investment-assets.page').then(
            (m) => m.InvestmentAssetsPage,
          ),
      },
    ],
  },
  { path: '**', redirectTo: '' },
];
