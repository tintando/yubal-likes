import type { LibraryFile } from "@/api/library";
import { Panel, PanelContent, PanelHeader } from "@/components/common/panel";
import {
  Button,
  Chip,
  Input,
  Popover,
  PopoverContent,
  PopoverTrigger,
  Spinner,
  Tooltip,
} from "@heroui/react";
import {
  FolderSearchIcon,
  MicVocalIcon,
  SearchIcon,
  Trash2Icon,
} from "lucide-react";
import { memo, useState } from "react";
import { useLibrarySearch } from "./use-library-search";

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function splitPath(path: string): { folder: string; filename: string } {
  const lastSlash = path.lastIndexOf("/");
  return {
    folder: lastSlash >= 0 ? path.slice(0, lastSlash) : "",
    filename: lastSlash >= 0 ? path.slice(lastSlash + 1) : path,
  };
}

const LibraryFileRow = memo(function LibraryFileRow({
  file,
  onDelete,
}: {
  file: LibraryFile;
  onDelete: (path: string) => Promise<void>;
}) {
  const [isDeleting, setIsDeleting] = useState(false);
  const { folder, filename } = splitPath(file.path);

  const handleDelete = async () => {
    setIsDeleting(true);
    try {
      await onDelete(file.path);
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="flex items-center gap-3 rounded-lg px-2 py-1.5 transition-colors hover:bg-default-100">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5">
          <p className="text-foreground text-small truncate font-mono">
            {filename}
          </p>
          {file.has_lyrics && (
            <Tooltip content="Has synced lyrics (.lrc)" closeDelay={0}>
              <MicVocalIcon className="text-foreground-400 h-3.5 w-3.5 shrink-0" />
            </Tooltip>
          )}
          {!file.in_playlist && (
            <Tooltip
              content="No playlist references this file — it will show up as an orphan"
              closeDelay={0}
            >
              <Chip
                size="sm"
                variant="flat"
                classNames={{
                  base: "bg-warning/15 text-warning-600 dark:text-warning-400 font-mono",
                }}
              >
                orphan
              </Chip>
            </Tooltip>
          )}
        </div>
        {folder && (
          <p className="text-foreground-400 text-tiny truncate">{folder}</p>
        )}
      </div>
      <span className="text-foreground-500 text-tiny shrink-0 font-mono">
        {formatSize(file.size)}
      </span>
      <Popover placement="top">
        <PopoverTrigger>
          <Button
            isIconOnly
            size="sm"
            variant="light"
            isLoading={isDeleting}
            aria-label="Delete file"
            className="shrink-0"
          >
            <Trash2Icon className="h-4 w-4" />
          </Button>
        </PopoverTrigger>
        <PopoverContent>
          <div className="flex flex-col gap-2 p-2">
            <p className="text-sm">
              Delete this file{file.has_lyrics ? " and its lyrics" : ""} (local
              and Drive)?
            </p>
            <Button size="sm" color="danger" onPress={handleDelete}>
              Delete
            </Button>
          </div>
        </PopoverContent>
      </Popover>
    </div>
  );
});

export function LibraryPanel() {
  const { query, setQuery, files, isLoading, hasSearched, deleteFile } =
    useLibrarySearch();

  return (
    <Panel>
      <PanelHeader
        leadingIcon={<FolderSearchIcon className="h-4 w-4" />}
        badge={
          hasSearched ? (
            <span className="text-foreground-400 text-xs">{files.length}</span>
          ) : undefined
        }
      >
        Library
      </PanelHeader>

      <div className="px-4 pb-2">
        <Input
          size="sm"
          placeholder="Search local files by name or folder..."
          value={query}
          onValueChange={setQuery}
          startContent={
            <SearchIcon className="text-foreground-400 h-4 w-4 shrink-0" />
          }
          isClearable
          onClear={() => setQuery("")}
          autoFocus
        />
      </div>

      <PanelContent height="h-[calc(100vh-16rem)]">
        {isLoading && files.length === 0 ? (
          <div className="flex h-full items-center justify-center">
            <Spinner size="lg" />
          </div>
        ) : !hasSearched ? (
          <div className="text-foreground-400 flex h-full items-center justify-center text-sm">
            Type to search your downloaded files
          </div>
        ) : files.length === 0 ? (
          <div className="text-foreground-400 flex h-full items-center justify-center text-sm">
            No files match your search
          </div>
        ) : (
          <div className="flex flex-col gap-0.5">
            {files.map((file) => (
              <LibraryFileRow
                key={file.path}
                file={file}
                onDelete={deleteFile}
              />
            ))}
          </div>
        )}
      </PanelContent>
    </Panel>
  );
}
