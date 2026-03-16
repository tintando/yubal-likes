import type { DriveStatus } from "@/api/drive";
import {
  Button,
  Dropdown,
  DropdownItem,
  DropdownMenu,
  DropdownTrigger,
  Link,
  Tooltip,
} from "@heroui/react";
import {
  HardDriveIcon,
  KeyRoundIcon,
  LogOutIcon,
  RefreshCwIcon,
  Trash2Icon,
  UploadIcon,
} from "lucide-react";

interface DriveDropdownProps {
  status: DriveStatus;
  isUploading: boolean;
  isDeleting: boolean;
  isAuthorizing: boolean;
  onDropdownAction: (key: React.Key) => void;
  onUploadClick: () => void;
  variant: "desktop" | "mobile";
}

export function DriveDropdown({
  status,
  isUploading,
  isDeleting,
  isAuthorizing,
  onDropdownAction,
  onUploadClick,
  variant,
}: DriveDropdownProps) {
  if (!status.enabled) return null;

  if (variant === "desktop") {
    // State 4: Fully authorized
    if (status.authorized) {
      return (
        <Dropdown>
          <DropdownTrigger>
            <Button
              isIconOnly
              size="sm"
              variant="light"
              aria-label="Drive options"
              isLoading={isDeleting || isAuthorizing}
            >
              <HardDriveIcon className="h-5 w-5 text-blue-500 dark:text-blue-300" />
            </Button>
          </DropdownTrigger>
          <AuthorizedMenu onAction={onDropdownAction} />
        </Dropdown>
      );
    }

    // State 3: Has client secrets, needs authorization
    if (status.has_client_secrets) {
      return (
        <Dropdown>
          <DropdownTrigger>
            <Button
              isIconOnly
              size="sm"
              variant="light"
              aria-label="Drive authorization needed"
              isLoading={isAuthorizing || isDeleting}
            >
              <HardDriveIcon className="h-5 w-5 text-amber-500 dark:text-amber-300" />
            </Button>
          </DropdownTrigger>
          <NeedsAuthMenu onAction={onDropdownAction} />
        </Dropdown>
      );
    }

    // State 2: No client secrets yet
    return (
      <Tooltip
        content="Upload OAuth client secrets for Google Drive"
        closeDelay={0}
      >
        <Button
          isIconOnly
          size="sm"
          variant="light"
          aria-label="Upload Drive client secrets"
          isLoading={isUploading}
          onPress={onUploadClick}
        >
          <HardDriveIcon className="h-5 w-5" />
        </Button>
      </Tooltip>
    );
  }

  // Mobile variant
  if (status.authorized) {
    return (
      <Dropdown>
        <DropdownTrigger>
          <Link
            as="button"
            color="foreground"
            className="w-full gap-2"
            size="lg"
          >
            Drive connected
          </Link>
        </DropdownTrigger>
        <AuthorizedMenu onAction={onDropdownAction} />
      </Dropdown>
    );
  }

  if (status.has_client_secrets) {
    return (
      <Dropdown>
        <DropdownTrigger>
          <Link
            as="button"
            color="foreground"
            className="w-full gap-2"
            size="lg"
          >
            Authorize Drive
          </Link>
        </DropdownTrigger>
        <NeedsAuthMenu onAction={onDropdownAction} />
      </Dropdown>
    );
  }

  return (
    <Link
      as="button"
      color="foreground"
      className="w-full cursor-pointer gap-2"
      size="lg"
      onPress={onUploadClick}
    >
      Upload Drive credentials
    </Link>
  );
}

interface MenuProps {
  onAction: (key: React.Key) => void;
}

function NeedsAuthMenu({ onAction }: MenuProps) {
  return (
    <DropdownMenu aria-label="Drive actions" onAction={onAction}>
      <DropdownItem
        key="authorize"
        startContent={<KeyRoundIcon className="h-4 w-4" />}
      >
        Authorize with Google
      </DropdownItem>
      <DropdownItem
        key="disconnect"
        color="danger"
        className="text-danger"
        startContent={<Trash2Icon className="h-4 w-4" />}
      >
        Delete client secrets
      </DropdownItem>
    </DropdownMenu>
  );
}

function AuthorizedMenu({ onAction }: MenuProps) {
  return (
    <DropdownMenu aria-label="Drive actions" onAction={onAction}>
      <DropdownItem
        key="reauthorize"
        startContent={<RefreshCwIcon className="h-4 w-4" />}
      >
        Re-authorize
      </DropdownItem>
      <DropdownItem
        key="upload"
        startContent={<UploadIcon className="h-4 w-4" />}
      >
        Upload new client secrets
      </DropdownItem>
      <DropdownItem
        key="disconnect"
        color="danger"
        className="text-danger"
        startContent={<LogOutIcon className="h-4 w-4" />}
      >
        Disconnect
      </DropdownItem>
    </DropdownMenu>
  );
}
