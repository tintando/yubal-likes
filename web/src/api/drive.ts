import { api } from "./client";

export interface DriveStatus {
  enabled: boolean;
  has_client_secrets: boolean;
  authorized: boolean;
  folder_id: string;
}

export async function getDriveStatus(): Promise<DriveStatus> {
  const { data, error } = await api.GET("/drive/status");
  if (error)
    return {
      enabled: false,
      has_client_secrets: false,
      authorized: false,
      folder_id: "",
    };
  return data;
}

export async function uploadDriveCredentials(
  content: string,
): Promise<boolean> {
  const { error } = await api.POST("/drive/credentials", {
    body: { content },
  });
  return !error;
}

export async function deleteDriveCredentials(): Promise<boolean> {
  const { error } = await api.DELETE("/drive/credentials");
  return !error;
}

export async function getDriveAuthUrl(): Promise<string | null> {
  const { data, error } = await api.GET("/drive/auth/url");
  if (error) return null;
  return data.url;
}
