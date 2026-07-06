import { api } from "./client";
import type { components } from "./schema";

export type LibraryFile = components["schemas"]["LibraryFile"];
export type LibrarySearchResponse = components["schemas"]["LibrarySearchResponse"];
export type LibraryDeleteResponse = components["schemas"]["LibraryDeleteResponse"];

export async function searchLibrary(query: string): Promise<LibrarySearchResponse> {
  const { data, error } = await api.GET("/api/library/search", {
    params: { query: { q: query } },
  });
  if (error) throw new Error("Failed to search library");
  return data;
}

export async function deleteLibraryFile(
  path: string,
): Promise<LibraryDeleteResponse> {
  const { data, error } = await api.POST("/api/library/delete", {
    body: { path },
  });
  if (error) throw new Error("Failed to delete file");
  return data;
}
