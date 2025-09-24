"""
Authentication API endpoints
"""
import hashlib
import secrets
from datetime import datetime
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, Response, Request, status
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm

from app.auth.dependencies import get_current_user, require_active_user
from app.auth.google_oauth import (
    GoogleOAuthError,
    GoogleTokenExchangeError,
    InvalidGoogleStateError,
    build_authorization_url,
    create_state_token,
    decode_state_token,
    exchange_code_for_tokens,
    resolve_post_login_redirect,
    verify_google_id_token,
)
from app.auth.security import create_access_token, create_refresh_token, hash_password, verify_password
from app.config import settings
from app.db.client import mongo_client
from app.db.models import AuthProvider, User, UserCreate, UserResponse, UserStatus

router = APIRouter(prefix="/auth", tags=["authentication"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate):
    """Register a new user with email and password"""
    
    # Check if user already exists
    existing_user = await mongo_client.database.users.find_one({"email": user_data.email})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    verification_token_plain = secrets.token_urlsafe(32)
    verification_token_hash = hashlib.sha256(verification_token_plain.encode()).hexdigest()

    user_doc = {
        "email": user_data.email,
        "password_hash": hash_password(user_data.password),
        "full_name": user_data.full_name,
        "auth_provider": AuthProvider.EMAIL.value,
        "status": UserStatus.PENDING.value,
        "email_verified": False,
        "total_searches": 0,
        "preferences": {},
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "email_verification_token_hash": verification_token_hash,
        "email_verification_sent_at": datetime.utcnow(),
    }
    
    result = await mongo_client.database.users.insert_one(user_doc)
    user_doc["_id"] = result.inserted_id

    _send_console_verification_email(
        email=user_doc["email"],
        token=verification_token_plain,
        full_name=user_doc.get("full_name") or user_doc["email"],
    )
    
    return UserResponse(
        id=str(user_doc["_id"]),
        email=user_doc["email"],
        full_name=user_doc["full_name"],
        auth_provider=str(user_doc["auth_provider"]),
        status=str(user_doc["status"]),
        email_verified=user_doc["email_verified"],
        total_searches=user_doc["total_searches"],
        created_at=user_doc["created_at"]
    )

@router.post("/login")
async def login(response: Response, form_data: OAuth2PasswordRequestForm = Depends()):
    """Login with email and password"""
    
    # Find user by email
    user_doc = await mongo_client.database.users.find_one({"email": form_data.username})
    if not user_doc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    if user_doc.get("password_hash") is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account uses Google sign-in. Please continue with Google OAuth."
        )

    # Verify password
    if not verify_password(form_data.password, user_doc["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    # Check if user is active
    if user_doc["status"] != UserStatus.ACTIVE.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account not active"
        )
    
    # Create tokens
    token_data = {"sub": str(user_doc["_id"]), "email": user_doc["email"]}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)
    
    # Update last login
    await mongo_client.database.users.update_one(
        {"_id": user_doc["_id"]},
        {"$set": {"last_login": datetime.utcnow(), "updated_at": datetime.utcnow(), "status": UserStatus.ACTIVE.value}}
    )
    
    # Set tokens in HTTP-only cookies
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
    response.set_cookie(
        key="refresh_token", 
        value=refresh_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    )
    
    return {
        "message": "Login successful",
        "user": UserResponse(
            id=str(user_doc["_id"]),
            email=user_doc["email"],
            full_name=user_doc["full_name"],
            auth_provider=str(user_doc["auth_provider"]),
            status=str(user_doc["status"]),
            email_verified=user_doc["email_verified"],
            total_searches=user_doc["total_searches"],
            created_at=user_doc["created_at"],
            last_login=datetime.utcnow()
        )
    }

@router.post("/logout")
async def logout(response: Response):
    """Logout by clearing cookies"""
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return {"message": "Logout successful"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: Optional[User] = Depends(get_current_user)):
    """Get current user information"""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        full_name=current_user.full_name,
        auth_provider=current_user.auth_provider,
        status=current_user.status,
        email_verified=current_user.email_verified,
        profile_picture=current_user.profile_picture,
        total_searches=current_user.total_searches,
        created_at=current_user.created_at,
        last_login=current_user.last_login
    )


@router.get("/google/login")
async def google_login(redirect_to: Optional[str] = Query(default=None, description="Optional relative path to redirect after login")):
    """Generate Google OAuth authorization URL and state token."""
    try:
        state_token = create_state_token(redirect_to)
        authorization_url = build_authorization_url(state_token)
    except GoogleOAuthError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    return {
        "authorization_url": authorization_url,
        "state": state_token,
        "provider": "google",
    }


@router.get("/google/callback")
async def google_callback(
    code: str,
    state: str,
    redirect_override: Optional[str] = Query(default=None, alias="redirect_to"),
):
    """Handle Google OAuth callback, creating or linking user accounts."""
    try:
        state_payload = decode_state_token(state)
    except InvalidGoogleStateError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    redirect_hint = redirect_override or state_payload.get("redirect_to")

    try:
        token_response = await exchange_code_for_tokens(code)
    except GoogleTokenExchangeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    id_token_value = token_response.get("id_token")
    if not id_token_value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Google token response missing id_token")

    try:
        id_payload = await verify_google_id_token(id_token_value)
    except GoogleOAuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    email = id_payload.get("email")
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Google account did not provide an email address")

    email_verified = bool(id_payload.get("email_verified", False))
    if settings.GOOGLE_REQUIRE_VERIFIED_EMAIL and not email_verified:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Google email address is not verified")

    provider_id = id_payload.get("sub")
    full_name = id_payload.get("name") or email.split("@")[0]
    picture = id_payload.get("picture")

    users_collection = mongo_client.database.users
    existing_user = await users_collection.find_one({"email": email})
    now = datetime.utcnow()

    if existing_user:
        updates = {
            "provider_id": provider_id or existing_user.get("provider_id"),
            "auth_provider": existing_user.get("auth_provider", AuthProvider.GOOGLE.value),
            "email_verified": existing_user.get("email_verified", False) or email_verified,
            "profile_picture": picture or existing_user.get("profile_picture"),
            "updated_at": now,
            "last_login": now,
        }

        status_value = existing_user.get("status")
        if email_verified and status_value in (UserStatus.PENDING.value, UserStatus.PENDING):
            updates["status"] = UserStatus.ACTIVE.value

        await users_collection.update_one({"_id": existing_user["_id"]}, {"$set": updates})
        user_doc = await users_collection.find_one({"_id": existing_user["_id"]})
    else:
        user_doc = {
            "email": email,
            "password_hash": None,
            "full_name": full_name,
            "auth_provider": AuthProvider.GOOGLE.value,
            "provider_id": provider_id,
            "status": UserStatus.ACTIVE.value if email_verified else UserStatus.PENDING.value,
            "email_verified": email_verified,
            "profile_picture": picture,
            "preferences": {},
            "total_searches": 0,
            "last_login": now,
            "created_at": now,
            "updated_at": now,
        }
        insert_result = await users_collection.insert_one(user_doc)
        user_doc["_id"] = insert_result.inserted_id

    token_data = {"sub": str(user_doc["_id"]), "email": user_doc.get("email")}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    redirect_target = resolve_post_login_redirect(redirect_hint)
    redirect_response = RedirectResponse(url=redirect_target, status_code=status.HTTP_303_SEE_OTHER)
    redirect_response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    redirect_response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
    )

    return redirect_response


@router.post("/verify-email")
async def verify_email(token: str = Query(..., description="Email verification token")):
    """Verify a user's email address using the token sent after registration."""
    if not token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Verification token is required")

    token_hash = hashlib.sha256(token.encode()).hexdigest()
    users_collection = mongo_client.database.users
    user_doc = await users_collection.find_one({"email_verification_token_hash": token_hash})

    if not user_doc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired verification token")

    updates = {
        "email_verified": True,
        "status": UserStatus.ACTIVE.value,
        "email_verification_token_hash": None,
        "email_verification_sent_at": None,
        "updated_at": datetime.utcnow(),
    }

    await users_collection.update_one({"_id": user_doc["_id"]}, {"$set": updates})
    refreshed = await users_collection.find_one({"_id": user_doc["_id"]})

    return {
        "message": "Email verified successfully",
        "user": UserResponse(
            id=str(refreshed["_id"]),
            email=refreshed["email"],
            full_name=refreshed.get("full_name"),
            auth_provider=str(refreshed.get("auth_provider", AuthProvider.EMAIL)),
            status=str(refreshed.get("status", UserStatus.ACTIVE)),
            email_verified=True,
            profile_picture=refreshed.get("profile_picture"),
            total_searches=refreshed.get("total_searches", 0),
            created_at=refreshed.get("created_at", datetime.utcnow()),
            last_login=refreshed.get("last_login"),
        ),
    }
def _send_console_verification_email(*, email: str, token: str, full_name: str) -> None:
    if settings.EMAIL_PROVIDER != "console":
        return
    verification_url = f"{settings.FRONTEND_BASE_URL.rstrip('/')}/verify-email?token={token}"
    print(
        "[EMAIL VERIFICATION]",
        f"To: {email}",
        f"Name: {full_name}",
        f"Link: {verification_url}",
        sep="\n"
    )
