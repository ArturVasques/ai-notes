import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { environment } from '../../../environments/environment';
import { authInterceptor } from './auth.interceptor';
import { AuthService } from './auth.service';

describe('authInterceptor', () => {
  const getAccessToken = vi.fn();
  let http: HttpClient;
  let controller: HttpTestingController;

  beforeEach(() => {
    getAccessToken.mockReset();
    getAccessToken.mockResolvedValue('access-token-value');

    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
        { provide: AuthService, useValue: { getAccessToken } },
      ],
    });

    http = TestBed.inject(HttpClient);
    controller = TestBed.inject(HttpTestingController);
  });

  afterEach(() => controller.verify());

  it('adds the Bearer token to API requests', async () => {
    http.get(`${environment.apiBaseUrl}/accounts`).subscribe();

    // The token is resolved asynchronously before the request is dispatched.
    const request = await vi.waitFor(() =>
      controller.expectOne(`${environment.apiBaseUrl}/accounts`),
    );

    expect(request.request.headers.get('Authorization')).toBe('Bearer access-token-value');
    expect(getAccessToken).toHaveBeenCalledOnce();
    request.flush([]);
  });

  it('leaves other origins untouched', () => {
    http.get('https://example.org/data').subscribe();

    const request = controller.expectOne('https://example.org/data');

    expect(request.request.headers.has('Authorization')).toBe(false);
    expect(getAccessToken).not.toHaveBeenCalled();
    request.flush({});
  });
});
