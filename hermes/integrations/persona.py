"""
PERSONA Integration

OAuth2/OIDC integration with PERSONA identity service.
"""

import uuid
from dataclasses import dataclass
from typing import Optional

import httpx
from jose import jwt, JWTError

from hermes.config import get_settings

settings = get_settings()


@dataclass
class User:
    """Authenticated user from PERSONA."""
    
    id: uuid.UUID
    username: str
    email: str
    display_name: str
    roles: list[str]
    teams: list[uuid.UUID]
    permissions: list[str]


class PersonaClient:
    """Client for PERSONA identity service."""

    def __init__(self):
        self.base_url = settings.persona_url
        self.client_id = settings.persona_client_id
        self.client_secret = settings.persona_client_secret
        self.algorithm = settings.jwt_algorithm
        self.audience = settings.jwt_audience
        self._jwks: Optional[dict] = None
        self._client = httpx.AsyncClient(timeout=30.0)

    async def get_jwks(self) -> dict:
        """Fetch JSON Web Key Set from PERSONA."""
        if self._jwks is None:
            response = await self._client.get(
                f"{self.base_url}/.well-known/jwks.json"
            )
            response.raise_for_status()
            self._jwks = response.json()
        return self._jwks

    async def validate_token(self, token: str) -> Optional[User]:
        """Validate a JWT access token and return user info."""
        try:
            # Get JWKS
            jwks = await self.get_jwks()

            # Decode and validate token
            payload = jwt.decode(
                token,
                jwks,
                algorithms=[self.algorithm],
                audience=self.audience,
            )

            # Extract user info
            return User(
                id=uuid.UUID(payload["sub"]),
                username=payload.get("preferred_username", ""),
                email=payload.get("email", ""),
                display_name=payload.get("name", ""),
                roles=payload.get("roles", []),
                teams=[uuid.UUID(t) for t in payload.get("teams", [])],
                permissions=payload.get("permissions", []),
            )
        except JWTError:
            return None

    async def get_user_info(self, token: str) -> Optional[dict]:
        """Fetch user info from PERSONA userinfo endpoint."""
        try:
            response = await self._client.get(
                f"{self.base_url}/userinfo",
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError:
            return None

    async def get_authorization_url(self, redirect_uri: str, state: str) -> str:
        """Generate OAuth2 authorization URL."""
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "scope": "openid profile email",
            "state": state,
        }
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{self.base_url}/authorize?{query}"

    async def exchange_code(self, code: str, redirect_uri: str) -> dict:
        """Exchange authorization code for tokens."""
        response = await self._client.post(
            f"{self.base_url}/token",
            data={
                "grant_type": "authorization_code",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
            },
        )
        response.raise_for_status()
        return response.json()

    async def refresh_token(self, refresh_token: str) -> dict:
        """Refresh access token."""
        response = await self._client.post(
            f"{self.base_url}/token",
            data={
                "grant_type": "refresh_token",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": refresh_token,
            },
        )
        response.raise_for_status()
        return response.json()

    async def close(self):
        """Close HTTP client."""
        await self._client.aclose()
