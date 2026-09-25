import { EnvironmentProviders, inject, provideAppInitializer, Provider } from '@angular/core';
import { MSAL_INSTANCE, MsalService } from '@azure/msal-angular';
import { BrowserCacheLocation, Configuration, PublicClientApplication } from '@azure/msal-browser';
import { environment } from '../../../environments/environment';

const msalConfig: Configuration = {
  auth: {
    clientId: environment.msal.clientId,
    authority: environment.msal.authority,
    redirectUri: environment.msal.redirectUri,
    postLogoutRedirectUri: environment.msal.postLogoutRedirectUri,
  },
  cache: {
    // Session storage: the account is forgotten when the browser session
    // ends. Re-evaluate for the installed PWA once it runs over HTTPS.
    cacheLocation: BrowserCacheLocation.SessionStorage,
  },
};

export function provideMsal(): (Provider | EnvironmentProviders)[] {
  return [
    {
      provide: MSAL_INSTANCE,
      useFactory: () => new PublicClientApplication(msalConfig),
    },
    MsalService,
    // MSAL must be initialized and the redirect response processed before
    // anything reads accounts or starts a login, so do it once before the
    // app renders.
    provideAppInitializer(async () => {
      const msal = inject(MSAL_INSTANCE);

      await msal.initialize();

      try {
        const result = await msal.handleRedirectPromise();
        const account = result?.account ?? msal.getAllAccounts()[0];

        if (account) {
          msal.setActiveAccount(account);
        }
      } catch (error) {
        // A failed or cancelled login must not prevent the app from starting.
        console.error('Login redirect failed', error);
      }
    }),
  ];
}
