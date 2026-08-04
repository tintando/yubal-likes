import {
  Avatar,
  Button,
  Modal,
  ModalBody,
  ModalContent,
  ModalFooter,
  ModalHeader,
  Spinner,
} from "@heroui/react";
import { CheckIcon } from "lucide-react";
import { useState } from "react";
import type { CookiesAccount } from "@/api/cookies";

interface AccountPickerModalProps {
  isOpen: boolean;
  onClose: () => void;
  accounts: CookiesAccount[];
  selected: string | null;
  isLoading: boolean;
  onPick: (authuser: string) => Promise<void>;
}

export function AccountPickerModal({
  isOpen,
  onClose,
  accounts,
  selected,
  isLoading,
  onPick,
}: AccountPickerModalProps) {
  const [pendingAuthuser, setPendingAuthuser] = useState<string | null>(null);

  const handlePick = async (authuser: string) => {
    setPendingAuthuser(authuser);
    try {
      await onPick(authuser);
    } finally {
      setPendingAuthuser(null);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="md">
      <ModalContent>
        <ModalHeader className="flex flex-col gap-1">
          Pick a YouTube account
          <span className="text-default-500 text-sm font-normal">
            Your cookies file holds sessions for every signed-in Google account.
            Choose the one whose Liked Music you want.
          </span>
        </ModalHeader>
        <ModalBody>
          {isLoading && accounts.length === 0 ? (
            <div className="flex justify-center py-8">
              <Spinner label="Probing accounts…" />
            </div>
          ) : accounts.length === 0 ? (
            <p className="text-default-500 py-4 text-sm">
              No accounts responded. Your cookies may be invalid or expired, so
              try re-exporting from a tab that's signed into YouTube Music.
            </p>
          ) : (
            <ul className="flex flex-col gap-2">
              {accounts.map((account) => {
                const isSelected = account.authuser === selected;
                const isPending = pendingAuthuser === account.authuser;
                return (
                  <li key={account.authuser}>
                    <button
                      type="button"
                      disabled={isPending}
                      onClick={() => handlePick(account.authuser)}
                      className="hover:bg-default-100 flex w-full items-center gap-3 rounded-lg p-3 text-left transition disabled:opacity-50"
                    >
                      <Avatar
                        src={account.accountPhotoUrl ?? undefined}
                        name={account.accountName}
                        size="md"
                      />
                      <div className="flex flex-1 flex-col">
                        <span className="font-medium">
                          {account.accountName}
                        </span>
                        {account.channelHandle && (
                          <span className="text-default-500 text-sm">
                            {account.channelHandle}
                          </span>
                        )}
                        <span className="text-default-400 text-xs">
                          authuser={account.authuser}
                        </span>
                      </div>
                      {isPending ? (
                        <Spinner size="sm" />
                      ) : isSelected ? (
                        <CheckIcon className="text-success h-5 w-5" />
                      ) : null}
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </ModalBody>
        <ModalFooter>
          <Button variant="light" onPress={onClose}>
            Close
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}
