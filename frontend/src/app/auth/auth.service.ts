import { computed, inject, Injectable, signal } from '@angular/core';
import { MsalService } from '@azure/msal-angular';
import { apiScopes } from './auth.config';

@Injectable({ providedIn: 'root' })
export class AuthService {
    private readonly msal = inject(MsalService);

    // The active account is set by the MSAL app initializer before the app
    // renders. Login is a full-page redirect, so it does not change later.
    readonly account = signal(this.msal.instance.getActiveAccount()).asReadonly();

    readonly isAuthenticated = computed(() => this.account() !== null);

    login(): void {
        this.msal.loginRedirect({
            scopes: apiScopes,
        });
    }

    logout(): void {
        const account = this.msal.instance.getActiveAccount();

        this.msal.logoutRedirect({
            account,
            postLogoutRedirectUri: 'http://localhost:4200',
        });
    }

    async getAccessToken(): Promise<string> {
        const account = this.msal.instance.getActiveAccount();

        if (!account) {
            throw new Error('No authenticated account');
        }

        const result = await this.msal.instance.acquireTokenSilent({
            account,
            scopes: apiScopes,
        });

        console.log('result: ', result)

        return result.accessToken;
    }
}
