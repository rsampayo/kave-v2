"""Tests for model documentation and schema correctness.

This module ensures that our database models are properly documented
and follow naming conventions.
"""

from typing import Any

import pytest
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.ext.declarative import DeclarativeMeta

from app.models.email_data import Attachment, Email, EmailAttachment
from app.schemas.webhook_schemas import DetailedWebhookResponse
from app.schemas.webhook_schemas import EmailAttachment as SchemaEmailAttachment
from app.schemas.webhook_schemas import (
    InboundEmailData,
    MailchimpWebhook,
    WebhookResponse,
)


def test_model_docstrings() -> None:
    """Test that all models have proper docstrings."""
    models = [Email, Attachment, EmailAttachment]

    for model in models:
        # Check class docstring
        assert model.__doc__, f"Model {model.__name__} is missing a docstring"
        assert (
            len(model.__doc__.strip()) > 10
        ), f"Model {model.__name__} has a too short docstring"


def test_model_attributes_documentation(monkeypatch: Any) -> None:
    """Test that model attributes have type annotations."""
    # Only test SQLAlchemy models
    models = [Email, Attachment]

    for model in models:
        # Get all mapped columns
        if isinstance(model, DeclarativeMeta):
            # Get mapped columns (not relationships)
            mapper = sa_inspect(model)
            for column in mapper.columns:
                attr = column.comment
                # Check if the column has a comment
                assert attr is not None, (
                    f"Column {column.name} in {model.__name__} "
                    f"has no documentation comment"
                )
                assert len(attr) > 5, (
                    f"Column {column.name} in {model.__name__} "
                    f"has a too short documentation comment"
                )


def test_schema_docstrings() -> None:
    """Test that all Pydantic schemas have proper docstrings."""
    schemas = [
        SchemaEmailAttachment,
        InboundEmailData,
        MailchimpWebhook,
        WebhookResponse,
        DetailedWebhookResponse,
    ]

    for schema in schemas:
        # Check class docstring
        assert schema.__doc__, f"Schema {schema.__name__} is missing a docstring"
        assert (
            len(schema.__doc__.strip()) > 10
        ), f"Schema {schema.__name__} has a too short docstring"


def test_schema_field_documentation() -> None:
    """Test that all schema fields have descriptions."""
    schemas = [
        SchemaEmailAttachment,
        InboundEmailData,
        MailchimpWebhook,
        WebhookResponse,
        DetailedWebhookResponse,
    ]

    for schema in schemas:
        # Get the schema fields
        for field_name, field in schema.model_fields.items():
            # Check that each field has a description
            msg = f"Field {field_name} in {schema.__name__} has no description"
            assert field.description, msg

            msg = f"Field {field_name} in {schema.__name__} has a too short description"
            assert len(field.description) > 5, msg


def test_schema_examples() -> None:
    """Test that response schemas have examples."""
    # These schemas should have examples
    schemas_with_examples = [MailchimpWebhook, WebhookResponse, DetailedWebhookResponse]

    for schema in schemas_with_examples:
        # Get model configuration
        assert hasattr(
            schema, "model_config"
        ), f"Schema {schema.__name__} has no model_config"
        config = schema.model_config

        # Check for examples or json_schema_extra
        assert (
            "json_schema_extra" in config
        ), f"Schema {schema.__name__} has no json_schema_extra in model_config"

        # Check that the example is meaningful
        json_schema_extra = config["json_schema_extra"]
        assert (
            "example" in json_schema_extra or "examples" in json_schema_extra
        ), f"Schema {schema.__name__} has no example/examples in json_schema_extra"


def test_model_and_schema_consistency() -> None:
    """Test consistency between database models and Pydantic schemas."""
    # Define mapping between models and schemas
    model_schema_pairs = [
        (Email, InboundEmailData),
        (Attachment, SchemaEmailAttachment),
    ]

    # Define field name mappings for common mismatches
    field_mapping = {
        # Schema field name -> Model field name
        "name": "filename",  # EmailAttachment.name -> Attachment.filename
        "type": "content_type",  # EmailAttachment.type -> Attachment.content_type
        "body_plain": "body_text",  # InboundEmailData.body_plain -> Email.body_text
    }

    for model, schema in model_schema_pairs:
        # Get all fields from the schema
        schema_fields = schema.model_fields.keys()

        # Get all columns from the model (excluding relationship fields)
        mapper = sa_inspect(model)
        if mapper is None:
            pytest.skip(f"Could not inspect model {model.__name__}")
            continue

        model_columns = [c.key for c in mapper.columns]

        # Check that fields in the schema have a column in the model
        for field in schema_fields:
            # Skip relationship fields and header dictionaries
            if field in ["attachments", "headers"]:
                continue

            # Check if we have a mapping for this field
            mapped_field = field_mapping.get(field, field)

            # Check if the mapped field exists in model columns
            if mapped_field not in model_columns:
                error_msg = (
                    f"Schema field {field!r} "
                    f"(mapped to {mapped_field!r}) "
                    f"in {schema.__name__} "
                    f"has no corresponding column"
                    f" in {model.__name__}"
                )
                pytest.fail(error_msg)


def test_response_schema_structure() -> None:
    """Test that response schemas have the needed fields and structure."""
    # Basic checks
    assert (
        "status" in WebhookResponse.model_fields
    ), "WebhookResponse is missing 'status' field"
    assert (
        "message" in WebhookResponse.model_fields
    ), "WebhookResponse is missing 'message' field"

    # Inheritance check
    assert issubclass(
        DetailedWebhookResponse, WebhookResponse
    ), "DetailedWebhookResponse should inherit from WebhookResponse"

    # DetailedWebhookResponse should have additional fields
    assert (
        "data" in DetailedWebhookResponse.model_fields
    ), "DetailedWebhookResponse is missing 'data' field"
    assert "processed_at" in DetailedWebhookResponse.model_fields, (
        "DetailedWebhookResponse is missing " "'processed_at' field"
    )
