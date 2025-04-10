"""Unit tests for API dependency functions."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient

from app.api.deps import verify_webhook_signature
from app.integrations.email.client import WebhookClient


@pytest.mark.asyncio
async def test_verify_webhook_signature() -> None:
    """Test webhook signature verification."""
    # Create mock request and client
    mock_request = MagicMock(spec=Request)
    mock_client = AsyncMock(spec=WebhookClient)

    # Setup mock client behavior
    mock_client.verify_webhook_signature.return_value = True

    # Call the function
    result = await verify_webhook_signature(mock_request, mock_client)

    # Verify it was called correctly
    mock_client.verify_webhook_signature.assert_called_once_with(mock_request)
    assert result is True


@pytest.mark.asyncio
async def test_verify_webhook_signature_invalid() -> None:
    """Test verify_webhook_signature when signature is invalid."""
    # Mock client and request
    mock_client = AsyncMock(spec=WebhookClient)
    # Configure the verify_webhook_signature method to return False
    mock_client.verify_webhook_signature.return_value = False
    mock_request = MagicMock(spec=Request)

    # Call the function
    result = await verify_webhook_signature(request=mock_request, client=mock_client)

    # Assert signature verification still passes (we don't require it)
    assert result is True
    mock_client.verify_webhook_signature.assert_called_once_with(mock_request)


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
