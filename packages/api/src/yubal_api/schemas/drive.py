"""Google Drive schemas."""

from typing import Literal

from pydantic import BaseModel


class DriveStatusResponse(BaseModel):
    """Drive configuration status."""

    enabled: bool
    has_client_secrets: bool
    authorized: bool
    folder_id: str


class DriveCredentialsUploadRequest(BaseModel):
    """Drive credentials upload request."""

    content: str


class DriveCredentialsResponse(BaseModel):
    """Drive credentials operation response."""

    status: Literal["ok"]


class DriveAuthUrlResponse(BaseModel):
    """Drive OAuth2 authorization URL response."""

    url: str
