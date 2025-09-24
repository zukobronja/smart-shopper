"""Tests for Google OAuth authentication endpoints."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict
from unittest.mock import AsyncMock, patch

import sys
from contextlib import asynccontextmanager

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT_DIR))

from backend.app.auth.google_oauth import create_state_token
from backend.app.auth.security import hash_password
from backend.app.config import settings
from backend.app.db import client as db_client
from backend.app.db.client import mongo_client
from backend.app.main import app
import backend.app.main as main_module
from backend.app.rss import ingestion_worker


class FakeUsersCollection:
    """Minimal async Mongo collection stub for testing."""

    def __init__(self) -> None:
        self.docs: Dict[str, Dict[str, Any]] = {}

    def _matches(self, document: Dict[str, Any], query: Dict[str, Any]) -> bool:
        for key, value in query.items():
            if key == "_id" and isinstance(value, ObjectId):
                if document.get("_id") != value:
                    return False
            else:
                if document.get(key) != value:
                    return False
        return True

    async def find_one(self, query: Dict[str, Any]) -> Dict[str, Any] | None:
        for doc in self.docs.values():
            if self._matches(doc, query):
                return doc.copy()
        return None

    async def insert_one(self, document: Dict[str, Any]):
        doc = document.copy()
        _id = doc.get("_id", ObjectId())
        doc["_id"] = _id
        self.docs[str(_id)] = doc
        return SimpleNamespace(inserted_id=_id)

    async def update_one(self, query: Dict[str, Any], update: Dict[str, Any]):
        for key, doc in self.docs.items():
            if self._matches(doc, query):
                set_values = update.get("$set", {})
                updated = doc.copy()
                updated.update(set_values)
                self.docs[key] = updated
                return SimpleNamespace(matched_count=1, modified_count=1)
        return SimpleNamespace(matched_count=0, modified_count=0)


@pytest.fixture(autouse=True)
def configure_google_settings(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "test-client-id")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setattr(settings, "GOOGLE_REDIRECT_URI", "http://testserver/auth/google/callback")
    monkeypatch.setattr(settings, "GOOGLE_ALLOWED_DOMAINS", [])
    monkeypatch.setattr(settings, "GOOGLE_REQUIRE_VERIFIED_EMAIL", True)
    monkeypatch.setattr(settings, "GOOGLE_OAUTH_SCOPES", ["openid", "email", "profile"])
    monkeypatch.setattr(settings, "FRONTEND_BASE_URL", "http://localhost:3000")
    yield


@pytest.fixture
def fake_users(monkeypatch):
    collection = FakeUsersCollection()
    database = SimpleNamespace(users=collection)
    monkeypatch.setattr(mongo_client, "database", database)
    monkeypatch.setattr(mongo_client, "client", SimpleNamespace())

    async def _noop(*args, **kwargs):  # type: ignore[unused-arg]
        return None

    monkeypatch.setattr(db_client, "connect_to_mongo", _noop)
    monkeypatch.setattr(db_client, "close_mongo_connection", _noop)
    monkeypatch.setattr(ingestion_worker, "start_worker", _noop)
    monkeypatch.setattr(ingestion_worker, "stop_worker", _noop)
    monkeypatch.setattr(main_module, "connect_to_mongo", _noop)
    monkeypatch.setattr(main_module, "close_mongo_connection", _noop)
    monkeypatch.setattr(main_module, "start_worker", _noop)
    monkeypatch.setattr(main_module, "stop_worker", _noop)

    @asynccontextmanager
    async def dummy_lifespan(app):  # type: ignore[unused-arg]
        yield

    monkeypatch.setattr(main_module, "lifespan", dummy_lifespan)
    main_module.app.router.lifespan_context = dummy_lifespan
    return collection


@pytest.fixture
def client(fake_users):
    with TestClient(app) as test_client:
        yield test_client


def test_google_login_generates_authorization_url(client):
    response = client.get("/auth/google/login", params={"redirect_to": "/dashboard"})
    assert response.status_code == 200

    payload = response.json()
    assert "authorization_url" in payload
    assert "state" in payload
    assert payload["provider"] == "google"
    assert "client_id=test-client-id" in payload["authorization_url"]
    assert "state=" in payload["authorization_url"]


def test_google_callback_creates_new_user(client, fake_users):
    state = create_state_token("/welcome")
    mock_tokens = {"id_token": "fake-id-token", "access_token": "fake-access"}
    mock_id_payload = {
        "sub": "google-user-123",
        "email": "new-user@example.com",
        "email_verified": True,
        "name": "New User",
        "picture": "https://example.com/avatar.png",
        "aud": "test-client-id",
        "iss": "https://accounts.google.com",
    }

    with patch("app.api.auth.exchange_code_for_tokens", AsyncMock(return_value=mock_tokens)), patch(
        "app.api.auth.verify_google_id_token", AsyncMock(return_value=mock_id_payload)
    ):
        response = client.get(
            "/auth/google/callback",
            params={"code": "auth-code", "state": state},
            allow_redirects=False,
        )

    assert response.status_code == 303
    assert response.headers["location"] == "http://localhost:3000/welcome"
    assert response.cookies.get("access_token") is not None
    assert len(fake_users.docs) == 1

    stored_user = next(iter(fake_users.docs.values()))
    assert stored_user["email"] == "new-user@example.com"
    assert str(stored_user["auth_provider"]) == "google"
    assert stored_user["provider_id"] == "google-user-123"
    assert stored_user["email_verified"] is True


def test_google_callback_links_existing_email_user(client, fake_users):
    existing_id = ObjectId()
    fake_users.docs[str(existing_id)] = {
        "_id": existing_id,
        "email": "existing@example.com",
        "password_hash": hash_password("password123"),
        "full_name": "Existing User",
        "auth_provider": "email",
        "provider_id": None,
        "status": "pending",
        "email_verified": False,
        "profile_picture": None,
        "preferences": {},
        "total_searches": 5,
        "last_login": None,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }

    state = create_state_token(None)
    mock_tokens = {"id_token": "fake-id-token"}
    mock_id_payload = {
        "sub": "google-existing-456",
        "email": "existing@example.com",
        "email_verified": True,
        "name": "Existing User",
        "picture": "https://example.com/new-avatar.png",
        "aud": "test-client-id",
        "iss": "https://accounts.google.com",
    }

    with patch("app.api.auth.exchange_code_for_tokens", AsyncMock(return_value=mock_tokens)), patch(
        "app.api.auth.verify_google_id_token", AsyncMock(return_value=mock_id_payload)
    ):
        response = client.get(
            "/auth/google/callback",
            params={"code": "auth-code", "state": state},
            allow_redirects=False,
        )

    assert response.status_code == 303
    stored_user = fake_users.docs[str(existing_id)]
    assert stored_user["provider_id"] == "google-existing-456"
    assert stored_user["email_verified"] is True
    assert stored_user["status"] == "active"
    assert stored_user["profile_picture"] == "https://example.com/new-avatar.png"
    assert response.cookies.get("access_token") is not None
