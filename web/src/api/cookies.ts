import { api } from "./client";

export async function getCookiesStatus(): Promise<boolean> {
  const { data, error } = await api.GET("/api/cookies/status");
  if (error) return false;
  return data.configured;
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
