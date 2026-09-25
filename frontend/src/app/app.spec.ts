import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { App } from './app';
import { AuthService } from './core/auth/auth.service';

describe('App', () => {
  const isAuthenticated = signal(false);
  const login = vi.fn();

  beforeEach(async () => {
    isAuthenticated.set(false);
    login.mockReset();

    await TestBed.configureTestingModule({
      imports: [App],
      providers: [{ provide: AuthService, useValue: { isAuthenticated, login } }],
    }).compileComponents();
  });

  it('shows the login button and starts login when signed out', async () => {
    const fixture = TestBed.createComponent(App);
    await fixture.whenStable();
    const button = (fixture.nativeElement as HTMLElement).querySelector('button');

    expect(button?.textContent).toContain('Login with Microsoft');

    button?.click();

    expect(login).toHaveBeenCalledOnce();
  });

  it('shows the authenticated state when signed in', async () => {
    isAuthenticated.set(true);
    const fixture = TestBed.createComponent(App);
    await fixture.whenStable();
    const compiled = fixture.nativeElement as HTMLElement;

    const buttons = Array.from(compiled.querySelectorAll('button')).map((button) =>
      button.textContent?.trim(),
    );

    expect(compiled.textContent).toContain('Authenticated');
    expect(buttons).toEqual(['Logout']);
  });
});
