import { computed, inject, Injectable, signal } from '@angular/core';
import { MsalService } from '@azure/msal-angular';
import { InteractionRequiredAuthError } from '@azure/msal-browser';
import { environment } from '../../../environments/environment';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly msal = inject(MsalService);

  // The active account is set by the MSAL app initializer before the app
  // renders. Login is a full-page redirect, so it does not change later.
  readonly account = signal(this.msal.instance.getActiveAccount()).asReadonly();

  readonly isAuthenticated = computed(() => this.account() !== null);

  readonly displayName = computed(() => {
    const account = this.account();
    return account?.name ?? account?.username ?? '';
  });

  login(): void {
    this.msal.loginRedirect({ scopes: environment.apiScopes });
  }

  logout(): void {
    this.msal.logoutRedirect({
      account: this.msal.instance.getActiveAccount(),
      postLogoutRedirectUri: environment.msal.postLogoutRedirectUri,
    });
  }

  /**
   * Access token for the API, from the MSAL cache or silently renewed.
   * When silent renewal is impossible (session expired, consent needed) the
   * user is sent through the login redirect instead of receiving an error.
   */
  async getAccessToken(): Promise<string> {
    const account = this.msal.instance.getActiveAccount();

    if (!account) {
      throw new Error('No authenticated account');
    }

    try {
      const result = await this.msal.instance.acquireTokenSilent({
        account,
        scopes: environment.apiScopes,
      });

      return result.accessToken;
    } catch (error) {
      if (error instanceof InteractionRequiredAuthError) {
        await this.msal.instance.acquireTokenRedirect({ account, scopes: environment.apiScopes });
      }

      throw error;
    }
  }
}
