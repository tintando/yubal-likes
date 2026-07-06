import { api } from "./client";

export interface CookiesStatus {
  configured: boolean;
  authuser: string | null;
}

export interface CookiesAccount {
  authuser: string;
  accountName: string;
  channelHandle: string | null;
  accountPhotoUrl: string | null;
}

export interface CookiesAccountsResponse {
  accounts: CookiesAccount[];
  selected: string;
}

export async function getCookiesStatus(): Promise<CookiesStatus> {
  const { data, error } = await api.GET("/api/cookies/status");
  if (error) return { configured: false, authuser: null };
  return { configured: data.configured, authuser: data.authuser ?? null };
}

export async function uploadCookies(content: string): Promise<boolean> {
  const { error } = await api.POST("/api/cookies", {
    body: { content },
  });
  return !error;
}

export async function deleteCookies(): Promise<boolean> {
  const { error } = await api.DELETE("/api/cookies");
  return !error;
}

export async function listAccounts(): Promise<CookiesAccountsResponse | null> {
  const { data, error } = await api.GET("/api/cookies/accounts");
  if (error) return null;
  return {
    accounts: data.accounts.map((account) => ({
      authuser: account.authuser,
      accountName: account.accountName,
      channelHandle: account.channelHandle ?? null,
      accountPhotoUrl: account.accountPhotoUrl ?? null,
    })),
    selected: data.selected,
  };
}

export async function selectAccount(authuser: string): Promise<boolean> {
  const { error } = await api.PUT("/api/cookies/account", {
    body: { authuser },
  });
  return !error;
}
