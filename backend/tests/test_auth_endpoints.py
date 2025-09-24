import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.auth import router as auth_router

@pytest.fixture
def app() -> FastAPI:
    app = FastAPI()
    app.include_router(auth_router)
    return app

@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)

@pytest.mark.skip("Not runnable in sandbox")
def test_me_requires_auth(client: TestClient):
    response = client.get("/auth/me")
    assert response.status_code == 401
