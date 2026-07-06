import {
  deleteLibraryFile,
  type LibraryFile,
  searchLibrary,
} from "@/api/library";
import { showErrorToast, showSuccessToast } from "@/lib/toast";
import { useCallback, useEffect, useRef, useState } from "react";

const DEBOUNCE_MS = 300;

export function useLibrarySearch() {
  const [query, setQuery] = useState("");
  const [files, setFiles] = useState<LibraryFile[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const requestIdRef = useRef(0);

  useEffect(() => {
    const trimmed = query.trim();
    if (!trimmed) {
      setFiles([]);
      setHasSearched(false);
      setIsLoading(false);
      return;
    }

    const requestId = ++requestIdRef.current;
    setIsLoading(true);
    const timer = setTimeout(async () => {
      try {
        const data = await searchLibrary(trimmed);
        if (requestId === requestIdRef.current) {
          setFiles(data.items);
          setHasSearched(true);
        }
      } catch {
        if (requestId === requestIdRef.current) {
          showErrorToast("Library", "Search failed");
        }
      } finally {
        if (requestId === requestIdRef.current) {
          setIsLoading(false);
        }
      }
    }, DEBOUNCE_MS);

    return () => clearTimeout(timer);
  }, [query]);

  const deleteFile = useCallback(async (path: string) => {
    try {
      const result = await deleteLibraryFile(path);
      setFiles((prev) => prev.filter((f) => f.path !== path));
      const drive = result.drive_files_deleted
        ? ` + ${result.drive_files_deleted} Drive`
        : "";
      showSuccessToast(
        "Library",
        `Deleted ${result.files_deleted.length} file${result.files_deleted.length !== 1 ? "s" : ""}${drive}`,
      );
    } catch {
      showErrorToast("Library", "Failed to delete file");
    }
  }, []);

  return { query, setQuery, files, isLoading, hasSearched, deleteFile };
}
