// Local development (`ng serve`). Same public identifiers as production;
// only the origins differ once the app is deployed.
export const environment = {
  production: false,
  apiBaseUrl: 'http://localhost:8000',
  msal: {
    clientId: 'a7f65d58-d33c-4d54-a58d-145f61cd0ee3',
    authority: 'https://login.microsoftonline.com/ff746bf4-ac21-4888-9492-329f890f03cf',
    redirectUri: 'http://localhost:4200',
    postLogoutRedirectUri: 'http://localhost:4200',
  },
  apiScopes: ['api://79c3be33-0729-4d58-b2ec-43db3a534c60/access_as_user'],
};
