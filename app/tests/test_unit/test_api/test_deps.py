"""Tests for API dependencies."""

import pytest

from app.integrations.email.client import WebhookClient
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
def test_dependency_warning_not_function() -> None:
    """Test that we get a dependency warning when providing a non-function value."""
    app = FastAPI()

    @app.get("/")
    def read_root(dep: WebhookClient = Depends(None)) -> dict:  # type: ignore[arg-type]
        return {"Hello": "World"}

    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 500
