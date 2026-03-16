"""Google Drive management endpoints."""

import asyncio
import logging

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from yubal_api.api.deps import SettingsDep
from yubal_api.schemas.drive import (
    DriveAuthUrlResponse,
    DriveCredentialsResponse,
    DriveCredentialsUploadRequest,
    DriveStatusResponse,
)
from yubal_api.services.gdrive_service import GDriveService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/drive", tags=["drive"])

SCOPES = ["https://www.googleapis.com/auth/drive.file"]

# Maps OAuth2 state -> code_verifier for PKCE flow
_pending_auth_states: dict[str, str | None] = {}


@router.get("/status")
async def drive_status(settings: SettingsDep) -> DriveStatusResponse:
    """Get Google Drive configuration status."""
    return DriveStatusResponse(
        enabled=settings.gdrive_enabled,
        has_client_secrets=settings.gdrive_client_configured,
        authorized=settings.gdrive_authorized,
        folder_id=settings.gdrive_folder_id,
    )


@router.post("/credentials")
async def upload_credentials(
    body: DriveCredentialsUploadRequest,
    settings: SettingsDep,
) -> DriveCredentialsResponse:
    """Upload OAuth2 client secrets JSON."""
    cred_path = settings.gdrive_client_secrets_file
    await asyncio.to_thread(cred_path.parent.mkdir, parents=True, exist_ok=True)
    await asyncio.to_thread(cred_path.write_text, body.content)
    return DriveCredentialsResponse(status="ok")


@router.delete("/credentials")
async def delete_credentials(request: Request, settings: SettingsDep) -> DriveCredentialsResponse:
    """Delete client secrets and token files."""
    for path in (settings.gdrive_client_secrets_file, settings.gdrive_token_file):
        if await asyncio.to_thread(path.exists):
            await asyncio.to_thread(path.unlink)

    # Clear gdrive_service since credentials are gone
    services = request.app.state.services
    services.gdrive_service = None
    services.job_executor._gdrive_service = None

    return DriveCredentialsResponse(status="ok")


@router.get("/auth/url")
async def get_auth_url(request: Request, settings: SettingsDep) -> DriveAuthUrlResponse:
    """Generate Google OAuth2 authorization URL."""
    from google_auth_oauthlib.flow import Flow

    redirect_uri = str(request.base_url).rstrip("/") + "/api/drive/auth/callback"

    flow = Flow.from_client_secrets_file(
        str(settings.gdrive_client_secrets_file),
        scopes=SCOPES,
        redirect_uri=redirect_uri,
    )

    auth_url, state = flow.authorization_url(
        access_type="offline",
        prompt="consent",
    )

    # Persist code_verifier so the callback can complete the PKCE exchange
    _pending_auth_states[state] = flow.code_verifier

    return DriveAuthUrlResponse(url=auth_url)


@router.get("/auth/callback")
async def auth_callback(
    request: Request, code: str, state: str, settings: SettingsDep
) -> RedirectResponse:
    """Handle Google OAuth2 callback, exchange code for tokens."""
    import json

    from google_auth_oauthlib.flow import Flow

    redirect_uri = str(request.base_url).rstrip("/") + "/api/drive/auth/callback"

    flow = Flow.from_client_secrets_file(
        str(settings.gdrive_client_secrets_file),
        scopes=SCOPES,
        redirect_uri=redirect_uri,
    )

    # Restore the code_verifier from the original auth request
    flow.code_verifier = _pending_auth_states.pop(state, None)

    await asyncio.to_thread(flow.fetch_token, code=code)

    credentials = flow.credentials
    token_data = {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": list(credentials.scopes) if credentials.scopes else SCOPES,
    }

    token_path = settings.gdrive_token_file
    await asyncio.to_thread(token_path.parent.mkdir, parents=True, exist_ok=True)
    await asyncio.to_thread(token_path.write_text, json.dumps(token_data))

    logger.info("Google Drive OAuth2 tokens saved successfully")

    # Hot-reload GDriveService
    services = request.app.state.services
    services.gdrive_service = GDriveService(
        token_file=settings.gdrive_token_file,
        root_folder_id=settings.gdrive_folder_id,
    )
    services.job_executor._gdrive_service = services.gdrive_service

    return RedirectResponse(url="/")
