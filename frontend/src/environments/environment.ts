// Production build configuration. Azure deployment is out of scope for v1,
// so these values still point at the local API; a deployment replaces this
// file (or the values) with the real origin and redirect URIs.
//
// Everything here is public configuration: MSAL is a public client and the
// identifiers below are not secrets.
export const environment = {
  production: true,
  apiBaseUrl: 'http://localhost:8000',
  msal: {
    clientId: 'a7f65d58-d33c-4d54-a58d-145f61cd0ee3',
    authority: 'https://login.microsoftonline.com/ff746bf4-ac21-4888-9492-329f890f03cf',
    redirectUri: 'http://localhost:4200',
    postLogoutRedirectUri: 'http://localhost:4200',
  },
  // Delegated scope of the API app registration. The API validates it.
  apiScopes: ['api://79c3be33-0729-4d58-b2ec-43db3a534c60/access_as_user'],
};
