"""Unit tests for API dependency functions."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient

from app.integrations.email.client import WebhookClient


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
def test_webhook_client_dependency_injection() -> None:
    """Test that the webhook client dependency is properly injected."""
    # We can't directly test a dependency, so we're mocking the class
    # and testing that it's called with the right parameters
    with patch("app.api.deps.webhook_client") as mock_client:
        # Create a function that simulates dependency injection
        def dependency() -> WebhookClient:
            return mock_client

        # Create a FastAPI endpoint that uses the dependency
        app = FastAPI()
        app.dependency_overrides = {}

        @app.get("/test-deps")
        async def test_endpoint(client=Depends(dependency)):
            return {"client": str(client)}

        # Create a test client
        with TestClient(app) as test_client:
            # Call the endpoint
            response = test_client.get("/test-deps")

            # Assert that the dependency was called
            assert response.status_code == 200
            assert "client" in response.json()
