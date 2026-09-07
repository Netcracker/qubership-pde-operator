export type HostConfig = {
  apiBase: string;
  routePrefix: string;
  credentials: RequestCredentials;
  tokenField: boolean;
  authHeaders(): Record<string, string>;
  getToken(): string;
  setToken(token: string): void;
};
