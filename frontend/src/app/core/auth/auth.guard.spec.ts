import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { ActivatedRouteSnapshot, RouterStateSnapshot, UrlTree } from '@angular/router';
import { anonymousGuard, authGuard } from './auth.guard';
import { AuthService } from './auth.service';

describe('auth guards', () => {
  const isAuthenticated = signal(false);
  const route = {} as ActivatedRouteSnapshot;
  const state = {} as RouterStateSnapshot;

  beforeEach(() => {
    isAuthenticated.set(false);
    TestBed.configureTestingModule({
      providers: [{ provide: AuthService, useValue: { isAuthenticated } }],
    });
  });

  it('sends signed-out visitors to the login page', () => {
    const result = TestBed.runInInjectionContext(() => authGuard(route, state));

    expect(result).toBeInstanceOf(UrlTree);
    expect((result as UrlTree).toString()).toBe('/login');
  });

  it('lets signed-in users through and keeps them off the login page', () => {
    isAuthenticated.set(true);

    expect(TestBed.runInInjectionContext(() => authGuard(route, state))).toBe(true);
    expect(
      (TestBed.runInInjectionContext(() => anonymousGuard(route, state)) as UrlTree).toString(),
    ).toBe('/');
  });
});
