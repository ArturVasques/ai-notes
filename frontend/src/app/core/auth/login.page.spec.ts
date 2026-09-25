import { TestBed } from '@angular/core/testing';
import { AuthService } from './auth.service';
import { LoginPage } from './login.page';

describe('LoginPage', () => {
  const login = vi.fn();

  beforeEach(async () => {
    login.mockReset();

    await TestBed.configureTestingModule({
      imports: [LoginPage],
      providers: [{ provide: AuthService, useValue: { login } }],
    }).compileComponents();
  });

  it('starts the Microsoft login', async () => {
    const fixture = TestBed.createComponent(LoginPage);
    await fixture.whenStable();
    const button = (fixture.nativeElement as HTMLElement).querySelector('button');

    expect(button?.textContent).toContain('Sign in with Microsoft');

    button?.click();

    expect(login).toHaveBeenCalledOnce();
  });
});
