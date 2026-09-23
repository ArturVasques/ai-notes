import { EnvironmentProviders, inject, provideAppInitializer, Provider } from '@angular/core';
import { MSAL_INSTANCE, MsalService } from '@azure/msal-angular';
import { BrowserCacheLocation, Configuration, PublicClientApplication } from '@azure/msal-browser';

const msalConfig: Configuration = {
  auth: {
    clientId: 'a7f65d58-d33c-4d54-a58d-145f61cd0ee3',
    authority: 'https://login.microsoftonline.com/ff746bf4-ac21-4888-9492-329f890f03cf',
    redirectUri: 'http://localhost:4200',
  },
  cache: {
    cacheLocation: BrowserCacheLocation.SessionStorage,
  },
};

export const apiScopes = [
  'api://79c3be33-0729-4d58-b2ec-43db3a534c60/access_as_user',
];

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
