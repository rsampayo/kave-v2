"""Tests for API documentation completeness and accuracy.

This module focuses on testing the documentation of our API endpoints,
ensuring they have proper descriptions, examples, and response models.
"""

from fastapi.openapi.utils import get_openapi
from fastapi.routing import APIRoute

from app.main import create_application


def test_api_endpoints_have_documentation() -> None:
    """Test that all API endpoints have proper documentation."""
    app = create_application()

    # Get all routes
    routes = [route for route in app.routes if isinstance(route, APIRoute)]

    for route in routes:
        # Check that every endpoint has a summary and description
        assert route.summary, f"Endpoint {route.path} is missing a summary"
        assert route.description, f"Endpoint {route.path} is missing a description"

        # Check that the function itself has a docstring
        assert (
            route.endpoint.__doc__
        ), f"Endpoint {route.path} handler is missing a docstring"


def test_openapi_schema_completeness() -> None:
    """Test that the OpenAPI schema is complete and contains all endpoints."""
    app = create_application()

    # Generate the OpenAPI schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    # Check that it has all the expected sections
    assert "paths" in openapi_schema, "OpenAPI schema is missing paths section"
    assert (
        "components" in openapi_schema
    ), "OpenAPI schema is missing components section"

    # Check for webhook endpoint in paths
    assert (
        "/v1/webhooks/mandrill" in openapi_schema["paths"]
    ), "Webhook endpoint not found in OpenAPI schema"


def test_webhook_schema_in_components() -> None:
    """Test that the webhook schema is defined in the components section."""
    app = create_application()

    # Generate the OpenAPI schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    # Check for webhook schema in components
    assert (
        "WebhookResponse" in openapi_schema["components"]["schemas"]
    ), "WebhookResponse schema not found in components"


def test_webhook_response_schemas() -> None:
    """Test that webhook endpoints have response schemas."""
    app = create_application()

    # Generate the OpenAPI schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    # Check for response schema in webhook endpoint
    webhook_endpoint = openapi_schema["paths"]["/v1/webhooks/mandrill"]["post"]
    assert (
        "responses" in webhook_endpoint
    ), "Webhook endpoint is missing responses section"

    # Check for 202 response
    assert (
        "202" in webhook_endpoint["responses"]
    ), "Webhook endpoint is missing 202 response"

    # Check for 500 response
    assert (
        "500" in webhook_endpoint["responses"]
    ), "Webhook endpoint is missing 500 response"
