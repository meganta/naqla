import secrets
from datetime import datetime, timedelta
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.database import get_db
from core.security import get_current_user
from modules.settings.service import get_tenant_settings

router = APIRouter(prefix="/auth", tags=["auth"])

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_SCOPES = "https://www.googleapis.com/auth/youtube.force-ssl"

_state_store: dict[str, str] = {}


@router.get("/google")
async def google_oauth_start(current_user=Depends(get_current_user)):
    state = secrets.token_urlsafe(32)
    _state_store[state] = current_user.tenant_id
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": f"{settings.api_url}/auth/google/callback",
        "response_type": "code",
        "scope": GOOGLE_SCOPES,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return {"auth_url": f"{GOOGLE_AUTH_URL}?{urlencode(params)}"}


@router.get("/google/callback")
async def google_oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    tenant_id = _state_store.pop(state, None)
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": f"{settings.api_url}/auth/google/callback",
                "grant_type": "authorization_code",
            },
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to exchange OAuth code")
        token_data = resp.json()

    tenant_settings = await get_tenant_settings(db, tenant_id)
    tenant_settings.google_access_token = token_data["access_token"]
    if "refresh_token" in token_data:
        tenant_settings.google_refresh_token = token_data["refresh_token"]
    expires_in = token_data.get("expires_in", 3600)
    tenant_settings.google_token_expiry = datetime.utcnow() + timedelta(seconds=expires_in)
    await db.commit()

    return {"location": f"{settings.frontend_url}/settings?google_connected=true"}


@router.get("/google/status")
async def google_oauth_status(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tenant_settings = await get_tenant_settings(db, current_user.tenant_id)
    connected = bool(tenant_settings.google_access_token)
    return {"connected": connected}
