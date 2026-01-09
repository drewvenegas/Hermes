"""
OIDC Authentication Routes

OAuth2/OIDC authentication flow with PERSONA.
"""

import secrets
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse

from hermes.config import get_settings

router = APIRouter(prefix="/auth", tags=["Authentication"])
settings = get_settings()

# In-memory state store (use Redis in production)
_state_store: dict[str, dict] = {}

# OIDC endpoints
PERSONA_BASE_URL = settings.persona_url
AUTHORIZE_URL = f"{PERSONA_BASE_URL}/oauth2/authorize"
TOKEN_URL = f"{PERSONA_BASE_URL}/oauth2/token"
USERINFO_URL = f"{PERSONA_BASE_URL}/oauth2/userinfo"
JWKS_URL = f"{PERSONA_BASE_URL}/oauth2/jwks"
LOGOUT_URL = f"{PERSONA_BASE_URL}/oauth2/logout"


@router.get("/login")
async def login(
    request: Request,
    redirect_uri: Optional[str] = Query(None, description="Post-login redirect URI"),
):
    """Initiate OIDC login flow.
    
    Redirects to PERSONA authorization endpoint.
    """
    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)
    
    # Store state with metadata
    _state_store[state] = {
        "created_at": datetime.utcnow().isoformat(),
        "redirect_uri": redirect_uri or "/",
    }
    
    # Build authorization URL
    callback_uri = f"{settings.app_url}/auth/callback"
    params = {
        "response_type": "code",
        "client_id": settings.persona_client_id,
        "redirect_uri": callback_uri,
        "scope": "openid profile email prompts:read prompts:write benchmarks:read",
        "state": state,
    }
    
    auth_url = f"{AUTHORIZE_URL}?{urlencode(params)}"
    return RedirectResponse(url=auth_url)


@router.get("/callback")
async def callback(
    request: Request,
    code: str = Query(..., description="Authorization code"),
    state: str = Query(..., description="State parameter"),
):
    """Handle OIDC callback.
    
    Exchanges authorization code for tokens.
    """
    # Validate state
    state_data = _state_store.pop(state, None)
    if not state_data:
        raise HTTPException(status_code=400, detail="Invalid or expired state")
    
    # Exchange code for tokens
    callback_uri = f"{settings.app_url}/auth/callback"
    token_data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": callback_uri,
        "client_id": settings.persona_client_id,
        "client_secret": settings.persona_client_secret,
    }
    
    async with httpx.AsyncClient() as client:
        try:
            token_response = await client.post(
                TOKEN_URL,
                data=token_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            token_response.raise_for_status()
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"Token exchange failed: {e}")
    
    tokens = token_response.json()
    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token")
    id_token = tokens.get("id_token")
    expires_in = tokens.get("expires_in", 3600)
    
    # Redirect to original destination with tokens in cookies
    redirect_uri = state_data.get("redirect_uri", "/")
    response = RedirectResponse(url=redirect_uri)
    
    # Set secure HTTP-only cookies
    response.set_cookie(
        key="hermes_access_token",
        value=access_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=expires_in,
    )
    if refresh_token:
        response.set_cookie(
            key="hermes_refresh_token",
            value=refresh_token,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=86400 * 7,  # 7 days
        )
    
    return response


@router.get("/logout")
async def logout(
    request: Request,
    redirect_uri: Optional[str] = Query(None, description="Post-logout redirect URI"),
):
    """Logout user.
    
    Clears session and redirects to PERSONA logout.
    """
    post_logout_uri = redirect_uri or settings.app_url
    
    # Build logout URL
    params = {
        "post_logout_redirect_uri": post_logout_uri,
        "client_id": settings.persona_client_id,
    }
    
    logout_url = f"{LOGOUT_URL}?{urlencode(params)}"
    response = RedirectResponse(url=logout_url)
    
    # Clear cookies
    response.delete_cookie("hermes_access_token")
    response.delete_cookie("hermes_refresh_token")
    
    return response


@router.get("/me")
async def get_current_user_info(request: Request):
    """Get current user information.
    
    Returns user profile from access token.
    """
    access_token = request.cookies.get("hermes_access_token")
    if not access_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Fetch user info from PERSONA
    async with httpx.AsyncClient() as client:
        try:
            userinfo_response = await client.get(
                USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            userinfo_response.raise_for_status()
        except httpx.HTTPError as e:
            raise HTTPException(status_code=401, detail=f"Failed to get user info: {e}")
    
    return userinfo_response.json()


@router.post("/refresh")
async def refresh_token(request: Request):
    """Refresh access token.
    
    Uses refresh token to get new access token.
    """
    refresh_token = request.cookies.get("hermes_refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token")
    
    token_data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": settings.persona_client_id,
        "client_secret": settings.persona_client_secret,
    }
    
    async with httpx.AsyncClient() as client:
        try:
            token_response = await client.post(
                TOKEN_URL,
                data=token_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            token_response.raise_for_status()
        except httpx.HTTPError as e:
            raise HTTPException(status_code=401, detail=f"Token refresh failed: {e}")
    
    tokens = token_response.json()
    access_token = tokens.get("access_token")
    new_refresh_token = tokens.get("refresh_token", refresh_token)
    expires_in = tokens.get("expires_in", 3600)
    
    response = Response(content='{"status": "refreshed"}', media_type="application/json")
    
    response.set_cookie(
        key="hermes_access_token",
        value=access_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=expires_in,
    )
    response.set_cookie(
        key="hermes_refresh_token",
        value=new_refresh_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=86400 * 7,
    )
    
    return response
