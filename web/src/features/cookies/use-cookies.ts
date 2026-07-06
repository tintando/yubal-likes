import { useCallback, useEffect, useRef, useState } from "react";
import {
  type CookiesAccount,
  deleteCookies,
  getCookiesStatus,
  listAccounts,
  selectAccount,
  uploadCookies,
} from "@/api/cookies";
import { showErrorToast, showSuccessToast } from "@/lib/toast";

interface UseCookiesReturn {
  cookiesConfigured: boolean;
  isUploading: boolean;
  isDeleting: boolean;
  accounts: CookiesAccount[];
  selectedAuthuser: string | null;
  isLoadingAccounts: boolean;
  isPickerOpen: boolean;
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  handleFileSelect: (e: React.ChangeEvent<HTMLInputElement>) => Promise<void>;
  handleDelete: () => Promise<void>;
  handleDropdownAction: (key: React.Key) => void;
  triggerFileUpload: () => void;
  openPicker: () => Promise<void>;
  closePicker: () => void;
  pickAccount: (authuser: string) => Promise<void>;
}

export function useCookies(): UseCookiesReturn {
  const [cookiesConfigured, setCookiesConfigured] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [accounts, setAccounts] = useState<CookiesAccount[]>([]);
  const [selectedAuthuser, setSelectedAuthuser] = useState<string | null>(null);
  const [isLoadingAccounts, setIsLoadingAccounts] = useState(false);
  const [isPickerOpen, setIsPickerOpen] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    getCookiesStatus()
      .then((status) => {
        setCookiesConfigured(status.configured);
        setSelectedAuthuser(status.authuser);
      })
      .catch(() => {
        // Fail silently - cookies status is non-critical
      });
  }, []);

  const loadAccounts = useCallback(async () => {
    setIsLoadingAccounts(true);
    try {
      const result = await listAccounts().catch(() => null);
      if (result) {
        setAccounts(result.accounts);
        setSelectedAuthuser(result.selected);
      }
      return result;
    } finally {
      setIsLoadingAccounts(false);
    }
  }, []);

  const handleFileSelect = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;

      setIsUploading(true);
      try {
        const content = await file.text();
        const success = await uploadCookies(content);

        if (!success) {
          showErrorToast("Upload failed", "Failed to upload cookies file");
          return;
        }

        setCookiesConfigured(true);
        setSelectedAuthuser(null);
        showSuccessToast(
          "Cookies uploaded",
          "YouTube cookies configured successfully",
        );

        // Discover Google accounts and prompt the user to pick the right one.
        // The cookies file may include sessions for multiple accounts; without
        // an explicit pick, YouTube defaults to the browser's primary account.
        setIsPickerOpen(true);
        const result = await loadAccounts();
        if (result && result.accounts.length <= 1) {
          // Only one account — no point in showing the picker.
          setIsPickerOpen(false);
        }
      } catch {
        showErrorToast("Upload failed", "Could not read the file");
      } finally {
        setIsUploading(false);
        if (fileInputRef.current) {
          fileInputRef.current.value = "";
        }
      }
    },
    [loadAccounts],
  );

  const handleDelete = useCallback(async () => {
    setIsDeleting(true);
    try {
      const success = await deleteCookies();
      if (success) {
        setCookiesConfigured(false);
        setAccounts([]);
        setSelectedAuthuser(null);
        showSuccessToast("Cookies deleted", "YouTube cookies removed");
      } else {
        showErrorToast("Delete failed", "Failed to delete cookies");
      }
    } catch {
      showErrorToast("Delete failed", "Could not delete cookies");
    } finally {
      setIsDeleting(false);
    }
  }, []);

  const triggerFileUpload = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const openPicker = useCallback(async () => {
    setIsPickerOpen(true);
    await loadAccounts();
  }, [loadAccounts]);

  const closePicker = useCallback(() => {
    setIsPickerOpen(false);
  }, []);

  const pickAccount = useCallback(async (authuser: string) => {
    const ok = await selectAccount(authuser).catch(() => false);
    if (ok) {
      setSelectedAuthuser(authuser);
      setIsPickerOpen(false);
      showSuccessToast("Account selected", "YouTube account updated");
    } else {
      showErrorToast("Selection failed", "Could not save account choice");
    }
  }, []);

  const handleDropdownAction = useCallback(
    (key: React.Key) => {
      if (key === "upload") {
        triggerFileUpload();
      } else if (key === "delete") {
        handleDelete();
      } else if (key === "switch") {
        openPicker();
      }
    },
    [triggerFileUpload, handleDelete, openPicker],
  );

  return {
    cookiesConfigured,
    isUploading,
    isDeleting,
    accounts,
    selectedAuthuser,
    isLoadingAccounts,
    isPickerOpen,
    fileInputRef,
    handleFileSelect,
    handleDelete,
    handleDropdownAction,
    triggerFileUpload,
    openPicker,
    closePicker,
    pickAccount,
  };
}
