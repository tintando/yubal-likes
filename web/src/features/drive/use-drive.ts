import { useCallback, useEffect, useRef, useState } from "react";
import {
  type DriveStatus,
  deleteDriveCredentials,
  getDriveAuthUrl,
  getDriveStatus,
  uploadDriveCredentials,
} from "@/api/drive";
import { showErrorToast, showSuccessToast } from "@/lib/toast";

interface UseDriveReturn {
  status: DriveStatus;
  isUploading: boolean;
  isDeleting: boolean;
  isAuthorizing: boolean;
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  handleFileSelect: (e: React.ChangeEvent<HTMLInputElement>) => Promise<void>;
  handleDropdownAction: (key: React.Key) => void;
  triggerFileUpload: () => void;
}

const DEFAULT_STATUS: DriveStatus = {
  enabled: false,
  has_client_secrets: false,
  authorized: false,
  folder_id: "",
};

export function useDrive(): UseDriveReturn {
  const [status, setStatus] = useState<DriveStatus>(DEFAULT_STATUS);
  const [isUploading, setIsUploading] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isAuthorizing, setIsAuthorizing] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    getDriveStatus()
      .then(setStatus)
      .catch(() => {});
  }, []);

  const handleFileSelect = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;

      setIsUploading(true);
      try {
        const content = await file.text();
        const success = await uploadDriveCredentials(content);

        if (success) {
          setStatus((prev) => ({ ...prev, has_client_secrets: true }));
          showSuccessToast(
            "Client secrets uploaded",
            "Now authorize with Google to complete setup",
          );
        } else {
          showErrorToast("Upload failed", "Failed to upload client secrets");
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
    [],
  );

  const handleDelete = useCallback(async () => {
    setIsDeleting(true);
    try {
      const success = await deleteDriveCredentials();
      if (success) {
        setStatus((prev) => ({
          ...prev,
          has_client_secrets: false,
          authorized: false,
        }));
        showSuccessToast("Disconnected", "Drive credentials removed");
      } else {
        showErrorToast("Delete failed", "Failed to delete credentials");
      }
    } catch {
      showErrorToast("Delete failed", "Could not delete credentials");
    } finally {
      setIsDeleting(false);
    }
  }, []);

  const handleAuthorize = useCallback(async () => {
    setIsAuthorizing(true);
    try {
      const url = await getDriveAuthUrl();
      if (url) {
        window.location.href = url;
      } else {
        showErrorToast(
          "Authorization failed",
          "Could not get authorization URL",
        );
        setIsAuthorizing(false);
      }
    } catch {
      showErrorToast("Authorization failed", "Could not start authorization");
      setIsAuthorizing(false);
    }
  }, []);

  const triggerFileUpload = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const handleDropdownAction = useCallback(
    (key: React.Key) => {
      if (key === "upload") {
        triggerFileUpload();
      } else if (key === "authorize" || key === "reauthorize") {
        handleAuthorize();
      } else if (key === "disconnect") {
        handleDelete();
      }
    },
    [triggerFileUpload, handleAuthorize, handleDelete],
  );

  return {
    status,
    isUploading,
    isDeleting,
    isAuthorizing,
    fileInputRef,
    handleFileSelect,
    handleDropdownAction,
    triggerFileUpload,
  };
}
