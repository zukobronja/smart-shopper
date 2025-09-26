"""Google OAuth helper utilities."""
from __future__ import annotations

import asyncio
import secrets
import time
from typing import Any, Dict, Optional
from urllib.parse import urlencode, urlparse

import httpx
import structlog
from jose import JWTError, jwt

from app.config import settings

logger = structlog.get_logger(__name__)

GOOGLE_AUTH_BASE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_OAUTH_STATE_TYPE = "google_oauth_state"
STATE_TOKEN_TTL_SECONDS = 600
ALLOWED_ISSUERS = {"https://accounts.google.com", "accounts.google.com"}


class GoogleOAuthError(Exception):
    """Base class for Google OAuth related errors."""


class InvalidGoogleStateError(GoogleOAuthError):
    """Raised when the OAuth state token is invalid or expired."""


class GoogleTokenExchangeError(GoogleOAuthError):
    """Raised when token exchange fails."""


def _ensure_google_oauth_config() -> None:
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise GoogleOAuthError(
            "Google OAuth is not fully configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.")


def _load_google_modules():
    """Safely import Google auth modules, raising a helpful error if missing."""
    try:
        from google.auth.transport import requests as google_requests_module
        from google.oauth2 import id_token as google_id_token_module
    except ImportError as exc:  # pragma: no cover - optional dependency missing
        raise GoogleOAuthError(
            "The 'google-auth' package is required for Google OAuth flows."
        ) from exc

    return google_requests_module, google_id_token_module


def _build_state_payload(redirect_to: Optional[str]) -> Dict[str, Any]:
    return {
        "nonce": secrets.token_urlsafe(16),
        "redirect_to": redirect_to,
        "type": GOOGLE_OAUTH_STATE_TYPE,
        "exp": int(time.time()) + STATE_TOKEN_TTL_SECONDS,
    }


def create_state_token(redirect_to: Optional[str] = None) -> str:
    """Create a signed state token that encodes redirect information."""
    payload = _build_state_payload(redirect_to)
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token


def decode_state_token(token: str) -> Dict[str, Any]:
    """Decode and validate a previously issued state token."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={"require_exp": True},
        )
    except JWTError as exc:
        raise InvalidGoogleStateError("Invalid or expired state token") from exc

    if payload.get("type") != GOOGLE_OAUTH_STATE_TYPE:
        raise InvalidGoogleStateError("Invalid state token type")

    return payload


def build_authorization_url(state_token: str) -> str:
    """Return a Google authorization URL for the given state token."""
    _ensure_google_oauth_config()

    scopes = settings.GOOGLE_OAUTH_SCOPES or ["openid", "email", "profile"]
    client_id = settings.google_client_ids[0] if settings.google_client_ids else settings.GOOGLE_CLIENT_ID

    params = {
        "client_id": client_id,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(scopes),
        "state": state_token,
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
    }

    return f"{GOOGLE_AUTH_BASE_URL}?{urlencode(params)}"


async def exchange_code_for_tokens(code: str) -> Dict[str, Any]:
    """Exchange an authorization code for tokens using Google's token endpoint."""
    _ensure_google_oauth_config()

    client_id = settings.google_client_ids[0] if settings.google_client_ids else settings.GOOGLE_CLIENT_ID

    data = {
        "code": code,
        "client_id": client_id,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    }

    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            GOOGLE_TOKEN_URL,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    if response.status_code != 200:
        logger.error(
            "Google token exchange failed",
            status_code=response.status_code,
            body=response.text,
        )
        raise GoogleTokenExchangeError("Failed to exchange authorization code for tokens")

    tokens = response.json()
    return tokens


async def verify_google_id_token(id_token_value: str) -> Dict[str, Any]:
    """Verify the ID token using Google's public keys and return the payload."""
    google_requests_module, google_id_token_module = _load_google_modules()
    request = google_requests_module.Request()
    loop = asyncio.get_running_loop()

    def _verify_sync() -> Dict[str, Any]:
        return google_id_token_module.verify_oauth2_token(id_token_value, request, audience=None)

    try:
        payload = await loop.run_in_executor(None, _verify_sync)
    except Exception as exc:  # noqa: BLE001 - wrap verification errors
        logger.error("Failed to verify Google ID token", error=str(exc))
        raise GoogleOAuthError("Failed to verify Google ID token") from exc

    aud = payload.get("aud")
    allowed_audiences = settings.google_client_ids or [settings.GOOGLE_CLIENT_ID]
    allowed_audiences = [audience for audience in allowed_audiences if audience]

    if allowed_audiences and aud not in allowed_audiences:
        logger.warning("Google ID token audience mismatch", audience=aud)
        raise GoogleOAuthError("Google ID token audience does not match configured client ID")

    iss = payload.get("iss")
    if iss not in ALLOWED_ISSUERS:
        logger.warning("Invalid Google ID token issuer", issuer=iss)
        raise GoogleOAuthError("Invalid Google ID token issuer")

    if settings.GOOGLE_ALLOWED_DOMAINS and not is_allowed_domain(payload):
        logger.warning("Google account domain not permitted", domain=payload.get("hd"))
        raise GoogleOAuthError("Google account domain is not allowed")

    return payload


def is_allowed_domain(payload: Dict[str, Any]) -> bool:
    """Check if the domain from the token payload is allowed."""
    if not settings.GOOGLE_ALLOWED_DOMAINS:
        return True

    token_domain = (payload.get("hd") or "").lower()
    if not token_domain and payload.get("email"):
        token_domain = payload["email"].split("@")[-1].lower()

    allowed = {domain.lower() for domain in settings.GOOGLE_ALLOWED_DOMAINS}
    return token_domain in allowed


def resolve_post_login_redirect(candidate: Optional[str]) -> str:
    """Resolve the final redirect target after successful OAuth login."""
    base = settings.FRONTEND_BASE_URL.rstrip("/") or "http://localhost:3000"

    if not candidate:
        return base

    candidate = candidate.strip()
    parsed_base = urlparse(base)

    if candidate.startswith("/"):
        return f"{base}{candidate}"

    parsed_candidate = urlparse(candidate)
    if (
        parsed_candidate.scheme == parsed_base.scheme
        and parsed_candidate.netloc == parsed_base.netloc
    ):
        return candidate

    # Fallback to base to avoid open redirects
    return base
