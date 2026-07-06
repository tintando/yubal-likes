"""Cookies management endpoints.

Handles YouTube Music authentication cookies in Netscape format.
Cookies enable access to private playlists and age-restricted content.
"""

import asyncio

from fastapi import APIRouter
from yubal.utils.cookies import list_authenticated_accounts

from yubal_api.api.deps import CookiesFileDep, SettingsDep, YtdlpDirDep
from yubal_api.api.exceptions import CookieValidationError
from yubal_api.schemas.cookies import (
    CookiesAccount,
    CookiesAccountSelectRequest,
    CookiesAccountsResponse,
    CookiesStatusResponse,
    CookiesUploadRequest,
    CookiesUploadResponse,
)

router = APIRouter(prefix="/cookies", tags=["cookies"])


def _validate_netscape_cookies(content: str) -> None:
    """Validate that content is in Netscape cookie format.

    Raises CookieValidationError if validation fails.
    """
    content = content.strip()
    if not content:
        raise CookieValidationError("Cookie file is empty")

    first_line = content.split("\n")[0]
    # Netscape format: starts with comment (# Netscape...) or domain entry
    if not first_line.startswith(("#", ".")):
        raise CookieValidationError(
            "Invalid cookie format. Expected Netscape format "
            "(file should start with '# Netscape HTTP Cookie File' or a domain entry)"
        )


@router.get("/status")
async def cookies_status(
    cookies_file: CookiesFileDep, settings: SettingsDep
) -> CookiesStatusResponse:
    """Check if cookies file is configured."""
    exists = await asyncio.to_thread(cookies_file.exists)
    authuser = settings.get_authuser() if exists else None
    return CookiesStatusResponse(configured=exists, authuser=authuser)


@router.post("")
async def upload_cookies(
    body: CookiesUploadRequest,
    cookies_file: CookiesFileDep,
    ytdlp_dir: YtdlpDirDep,
    settings: SettingsDep,
) -> CookiesUploadResponse:
    """Upload cookies.txt content (Netscape format).

    The cookie file enables downloading from private playlists
    and accessing age-restricted content on YouTube Music.
    """
    _validate_netscape_cookies(body.content)

    await asyncio.to_thread(ytdlp_dir.mkdir, parents=True, exist_ok=True)
    await asyncio.to_thread(cookies_file.write_text, body.content)

    # Reset selected account on new upload — old index may not match new cookies.
    await asyncio.to_thread(settings.authuser_file.unlink, missing_ok=True)

    return CookiesUploadResponse(status="ok")


@router.delete("")
async def delete_cookies(
    cookies_file: CookiesFileDep, settings: SettingsDep
) -> CookiesUploadResponse:
    """Delete the cookies file and the account selection that goes with it."""
    await asyncio.to_thread(cookies_file.unlink, missing_ok=True)
    await asyncio.to_thread(settings.authuser_file.unlink, missing_ok=True)
    return CookiesUploadResponse(status="ok")


@router.get("/accounts")
async def list_accounts(
    cookies_file: CookiesFileDep, settings: SettingsDep
) -> CookiesAccountsResponse:
    """Discover Google accounts available with the current cookies file.

    Browser cookie exports include session data for every account signed in
    to that browser. The ``x-goog-authuser`` header tells YouTube which one
    to use; this endpoint probes indices 0..4 and returns the names of any
    accounts that respond, so the user can pick the right one.
    """
    if not await asyncio.to_thread(cookies_file.exists):
        return CookiesAccountsResponse(accounts=[], selected=settings.get_authuser())

    raw = await asyncio.to_thread(list_authenticated_accounts, cookies_file)
    accounts = [CookiesAccount.model_validate(a) for a in raw]
    return CookiesAccountsResponse(accounts=accounts, selected=settings.get_authuser())


@router.put("/account")
async def select_account(
    body: CookiesAccountSelectRequest,
    settings: SettingsDep,
    ytdlp_dir: YtdlpDirDep,
) -> CookiesUploadResponse:
    """Persist the chosen Google account index for cookies.txt."""
    authuser = body.authuser.strip()
    if not (authuser.isascii() and authuser.isdigit()):
        raise CookieValidationError("authuser must be a non-negative integer")
    await asyncio.to_thread(ytdlp_dir.mkdir, parents=True, exist_ok=True)
    await asyncio.to_thread(settings.authuser_file.write_text, authuser)
    return CookiesUploadResponse(status="ok")
