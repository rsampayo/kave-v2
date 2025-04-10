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
        "/webhooks/mandrill" in openapi_schema["paths"]
    ), "Webhook endpoint not found in OpenAPI schema"

    # Check that the webhook endpoint has the expected operations
    webhook_endpoint = openapi_schema["paths"]["/webhooks/mandrill"]
    assert "post" in webhook_endpoint, "POST operation missing from webhook endpoint"

    # Check response descriptions
    post_operation = webhook_endpoint["post"]
    assert "responses" in post_operation, "No responses defined for webhook endpoint"
    assert (
        "202" in post_operation["responses"]
    ), "No 202 response defined for webhook endpoint"
    assert (
        "500" in post_operation["responses"]
    ), "No 500 response defined for webhook endpoint"


def test_webhook_schema_in_components() -> None:
    """Test that webhook schemas are properly defined in the OpenAPI components."""
    app = create_application()

    # Generate the OpenAPI schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    # Check for schema components
    schemas = openapi_schema["components"]["schemas"]

    # Check that response schema exists in the components
    assert (
        "WebhookResponse" in schemas
    ), "WebhookResponse schema not found in components"

    # Check that the schema has properties
    webhook_response_schema = schemas["WebhookResponse"]
    assert (
        "properties" in webhook_response_schema
    ), "WebhookResponse schema has no properties defined"

    # Check for required status and message fields
    properties = webhook_response_schema["properties"]
    assert "status" in properties, "WebhookResponse schema is missing status property"
    assert "message" in properties, "WebhookResponse schema is missing message property"

    # Check for example
    assert (
        "example" in webhook_response_schema
    ), "WebhookResponse schema is missing an example"


def test_webhook_response_schemas() -> None:
    """Test that the webhook endpoint defines proper response schemas."""
    app = create_application()

    # Generate the OpenAPI schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    # Get the webhook endpoint
    webhook_endpoint = openapi_schema["paths"]["/webhooks/mandrill"]
    post_operation = webhook_endpoint["post"]

    # Check response content
    responses = post_operation["responses"]

    # Success response
    assert "202" in responses, "No 202 response defined"
    response_202 = responses["202"]
    assert "description" in response_202, "202 response is missing a description"
    assert "content" in response_202, "202 response is missing content specification"

    # Error response
    assert "500" in responses, "No 500 response defined"
    response_500 = responses["500"]
    assert "description" in response_500, "500 response is missing a description"
    assert "content" in response_500, "500 response is missing content specification"
