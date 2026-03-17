import { AnimatedThemeToggler } from "@/components/magicui/animated-theme-toggler";
import { CookieDropdown } from "@/features/cookies/cookie-dropdown";
import { useCookies } from "@/features/cookies/use-cookies";
import { DriveDropdown } from "@/features/drive/drive-dropdown";
import { useDrive } from "@/features/drive/use-drive";
import { useJobs } from "@/features/jobs/jobs-context";
import { useVersionCheck } from "@/hooks/use-version-check";
import {
  Button,
  Link as HeroUILink,
  Navbar,
  NavbarBrand,
  NavbarContent,
  NavbarItem,
  NavbarMenu,
  NavbarMenuItem,
  NavbarMenuToggle,
} from "@heroui/react";
import { Link } from "@tanstack/react-router";
import {
  Disc3Icon,
  RocketIcon,
  StarIcon,
} from "lucide-react";
import { useState } from "react";

export function Header() {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const {
    cookiesConfigured,
    isUploading,
    isDeleting,
    fileInputRef,
    handleFileSelect,
    handleDropdownAction,
    triggerFileUpload,
  } = useCookies();
  const {
    status: driveStatus,
    isUploading: isDriveUploading,
    isDeleting: isDriveDeleting,
    isAuthorizing: isDriveAuthorizing,
    fileInputRef: driveFileInputRef,
    handleFileSelect: handleDriveFileSelect,
    handleDropdownAction: handleDriveDropdownAction,
    triggerFileUpload: triggerDriveFileUpload,
  } = useDrive();
  const { data: versionInfo } = useVersionCheck();
  const { hasActiveJobs } = useJobs();

  return (
    <Navbar
      isMenuOpen={isMenuOpen}
      onMenuOpenChange={setIsMenuOpen}
      classNames={{
        wrapper: "max-w-5xl",
        brand: "grow-0",
      }}
    >
      {/* Mobile menu toggle + Brand */}
      <NavbarContent className="sm:hidden" justify="start">
        <NavbarMenuToggle
          aria-label={isMenuOpen ? "Close menu" : "Open menu"}
        />
      </NavbarContent>

      <NavbarBrand className="mr-4">
        <Link to="/" className="flex items-center">
          <Disc3Icon
            className={`text-primary h-7 w-7 ${hasActiveJobs ? "animate-[spin_4s_linear_infinite] motion-reduce:animate-none" : ""}`}
          />
          <p className="text-foreground ml-2 text-xl font-bold">yubal</p>
        </Link>
      </NavbarBrand>

      {/* Actions */}
      <NavbarContent className="items-center gap-2" justify="end">
        {versionInfo?.updateAvailable && (
          <NavbarItem className="hidden sm:flex">
            <Button
              as="a"
              disableAnimation
              size="sm"
              href={versionInfo.releaseUrl}
              target="_blank"
              rel="noopener noreferrer"
              variant="flat"
              color="success"
              radius="lg"
              startContent={<RocketIcon className="h-4 w-4" />}
              className="text-small font-mono"
            >
              {versionInfo.latestVersion}
            </Button>
          </NavbarItem>
        )}
        <NavbarItem className="hidden sm:flex">
          <Button
            as="a"
            disableAnimation
            size="sm"
            href="https://github.com/guillevc/yubal"
            target="_blank"
            rel="noopener noreferrer"
            variant="light"
            radius="lg"
            startContent={
              <StarIcon
                className="h-4 w-4 fill-amber-400 text-amber-400 dark:fill-amber-300 dark:text-amber-300"
                strokeWidth={1}
              />
            }
            className="text-small"
          >
            Star on GitHub
          </Button>
        </NavbarItem>
        <NavbarItem className="hidden sm:flex">
          <DriveDropdown
            variant="desktop"
            status={driveStatus}
            isUploading={isDriveUploading}
            isDeleting={isDriveDeleting}
            isAuthorizing={isDriveAuthorizing}
            onDropdownAction={handleDriveDropdownAction}
            onUploadClick={triggerDriveFileUpload}
          />
        </NavbarItem>
        <NavbarItem className="hidden sm:flex">
          <CookieDropdown
            variant="desktop"
            cookiesConfigured={cookiesConfigured}
            isUploading={isUploading}
            isDeleting={isDeleting}
            onDropdownAction={handleDropdownAction}
            onUploadClick={triggerFileUpload}
          />
        </NavbarItem>
        <NavbarItem>
          <AnimatedThemeToggler />
        </NavbarItem>
      </NavbarContent>

      {/* Mobile menu */}
      <NavbarMenu>
        <NavbarMenuItem>
          <CookieDropdown
            variant="mobile"
            cookiesConfigured={cookiesConfigured}
            isUploading={isUploading}
            isDeleting={isDeleting}
            onDropdownAction={handleDropdownAction}
            onUploadClick={triggerFileUpload}
          />
        </NavbarMenuItem>
        {driveStatus.enabled && (
          <NavbarMenuItem>
            <DriveDropdown
              variant="mobile"
              status={driveStatus}
              isUploading={isDriveUploading}
              isDeleting={isDriveDeleting}
              isAuthorizing={isDriveAuthorizing}
              onDropdownAction={handleDriveDropdownAction}
              onUploadClick={triggerDriveFileUpload}
            />
          </NavbarMenuItem>
        )}
        <NavbarMenuItem>
          <HeroUILink
            href="https://github.com/guillevc/yubal"
            isExternal
            showAnchorIcon
            color="foreground"
            className="w-full"
            size="lg"
          >
            Star on GitHub
          </HeroUILink>
        </NavbarMenuItem>
      </NavbarMenu>

      {/* Hidden file inputs for uploads */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".txt"
        onChange={handleFileSelect}
        className="hidden"
      />
      <input
        ref={driveFileInputRef}
        type="file"
        accept=".json"
        onChange={handleDriveFileSelect}
        className="hidden"
      />
    </Navbar>
  );
}
