import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from './auth.service';

/** Sends signed-out visitors to the login page. */
export const authGuard: CanActivateFn = () => {
  const auth = inject(AuthService);

  if (auth.isAuthenticated()) {
    return true;
  }

  return inject(Router).createUrlTree(['/login']);
};

/** Keeps signed-in users away from the login page. */
export const anonymousGuard: CanActivateFn = () => {
  const auth = inject(AuthService);

  if (!auth.isAuthenticated()) {
    return true;
  }

  return inject(Router).createUrlTree(['/']);
};
