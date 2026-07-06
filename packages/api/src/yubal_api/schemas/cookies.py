"""Cookies schemas."""

from typing import Literal

from pydantic import BaseModel


class CookiesStatusResponse(BaseModel):
    """Cookies status response model."""

    configured: bool
    authuser: str | None = None


class CookiesUploadRequest(BaseModel):
    """Cookies upload request model."""

    content: str


class CookiesUploadResponse(BaseModel):
    """Cookies upload response model."""

    status: Literal["ok"]


class CookiesAccount(BaseModel):
    """One Google account discovered in the cookies file."""

    authuser: str
    accountName: str
    channelHandle: str | None = None
    accountPhotoUrl: str | None = None


class CookiesAccountsResponse(BaseModel):
    """Discovered accounts and currently selected authuser index."""

    accounts: list[CookiesAccount]
    selected: str


class CookiesAccountSelectRequest(BaseModel):
    """Request to set the active Google account."""

    authuser: str
