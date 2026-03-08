"""Shared fixtures for integration tests."""
import os
import uuid
from typing import AsyncGenerator

import httpx
import pytest

BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")


@pytest.fixture
def session_id() -> str:
    """Fresh UUID session ID per test — mirrors what a real client would generate."""
    return str(uuid.uuid4())


@pytest.fixture
async def client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Async HTTP client pointed at the running API server."""
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as c:
        yield c
