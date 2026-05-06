"""Test configuration and fixtures."""
import os
import sys

import httpx
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

BASE_URL = os.environ.get("MINDPILOT_URL", "http://127.0.0.1:8000")


@pytest.fixture
def client():
    """Sync HTTP client for testing."""
    return httpx.Client(base_url=BASE_URL, timeout=60.0)


@pytest.fixture
def async_client():
    """Async HTTP client for testing."""
    return httpx.AsyncClient(base_url=BASE_URL, timeout=60.0)


@pytest.fixture
def auth_token():
    """Get a valid JWT token for testing."""
    with httpx.Client(base_url=BASE_URL, timeout=30.0) as c:
        resp = c.post("/api/auth/register", json={
            "username": f"test_user_{os.getpid()}",
            "password": "test123456",
            "email": "test@mindpilot.test",
        })
        if resp.status_code == 200:
            return resp.json()["access_token"]
        # Try login if already exists
        resp = c.post("/api/auth/login", json={
            "username": f"test_user_{os.getpid()}",
            "password": "test123456",
        })
        if resp.status_code == 200:
            return resp.json()["access_token"]
        return ""
