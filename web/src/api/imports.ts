export type ImportResult =
  | { success: true; jobId: string }
  | { success: false; error: string };

export async function importFiles(files: File[]): Promise<ImportResult> {
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file);
  }

  try {
    const response = await fetch("/api/imports", {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const body = await response.json().catch(() => null);
      const error =
        body?.detail ?? body?.error ?? `Upload failed (${response.status})`;
      return { success: false, error };
    }

    const data = await response.json();
    return { success: true, jobId: data.id };
  } catch {
    return { success: false, error: "Network error" };
  }
}
