"""Module providing Organization Schema functionality."""

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr


class OrganizationBase(BaseModel):
    """Base schema for organization data."""

    name: str = Field(..., description="Name of the organization")
    webhook_email: EmailStr = Field(
        ..., description="Email address that will be sending webhooks"
    )


class OrganizationCreate(OrganizationBase):
    """Schema for creating a new organization."""

    mandrill_api_key: str = Field(
        ..., description="Mandrill API key for this organization"
    )
    mandrill_webhook_secret: str = Field(
        ..., description="Mandrill webhook secret for this organization"
    )


class OrganizationUpdate(BaseModel):
    """Schema for updating an organization."""

    name: str | None = Field(None, description="Name of the organization")
    webhook_email: EmailStr | None = Field(
        None, description="Email address that will be sending webhooks"
    )
    mandrill_api_key: str | None = Field(
        None, description="Mandrill API key for this organization"
    )
    mandrill_webhook_secret: str | None = Field(
        None, description="Mandrill webhook secret for this organization"
    )
    is_active: bool | None = Field(
        None, description="Whether this organization's webhooks are active"
    )


class OrganizationInDB(OrganizationBase):
    """Schema for organization data stored in the database."""

    id: int = Field(..., description="Unique identifier for the organization")
    mandrill_api_key: SecretStr = Field(
        ..., description="Mandrill API key for this organization"
    )
    mandrill_webhook_secret: SecretStr = Field(
        ..., description="Mandrill webhook secret for this organization"
    )
    is_active: bool = Field(
        ..., description="Whether this organization's webhooks are active"
    )

    model_config = ConfigDict(from_attributes=True)


class OrganizationResponse(OrganizationBase):
    """Schema for organization API responses."""

    id: int = Field(..., description="Unique identifier for the organization")
    mandrill_api_key: str = Field(
        ..., description="Mandrill API key for this organization"
    )
    mandrill_webhook_secret: str = Field(
        ..., description="Mandrill webhook secret for this organization"
    )
    is_active: bool = Field(
        ..., description="Whether this organization's webhooks are active"
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "name": "Example Organization",
                "webhook_email": "webhooks@example.com",
                "mandrill_api_key": "api-key-example-123",
                "mandrill_webhook_secret": "webhook-secret-example-123",
                "is_active": True,
            }
        },
    )
