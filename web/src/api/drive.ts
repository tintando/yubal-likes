import { api } from "./client";

export interface DriveStatus {
  enabled: boolean;
  has_client_secrets: boolean;
  authorized: boolean;
  folder_id: string;
}

export async function getDriveStatus(): Promise<DriveStatus> {
  const { data, error } = await api.GET("/api/drive/status");
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
  const { error } = await api.POST("/api/drive/credentials", {
    body: { content },
  });
  return !error;
}

export async function deleteDriveCredentials(): Promise<boolean> {
  const { error } = await api.DELETE("/api/drive/credentials");
  return !error;
}

export async function getDriveAuthUrl(): Promise<string | null> {
  const { data, error } = await api.GET("/api/drive/auth/url");
  if (error) return null;
  return data.url;
}

export interface DriveUploadResult {
  files_uploaded: number;
  files_skipped: number;
  files_cleaned: number;
}

export async function uploadLibraryToDrive(): Promise<DriveUploadResult> {
  const { data, error } = await api.POST("/api/drive/upload");
  if (error) {
    const detail =
      error && typeof error === "object" && "detail" in error
        ? String((error as { detail: unknown }).detail)
        : "Drive upload failed";
    throw new Error(detail);
  }
  return data;
}
