"""Tests for organization endpoints."""

import uuid

import pytest
from fastapi import status
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_create_organization(async_client: AsyncClient, db_session, setup_db):
    """Test creating a new organization."""
    unique_id = str(uuid.uuid4()).split("-")[0]
    data = {
        "name": f"Test Organization {unique_id}",
        "webhook_email": f"test_{unique_id}@example.com",
        "mandrill_api_key": f"test-api-key-{unique_id}",
        "mandrill_webhook_secret": f"test-webhook-secret-{unique_id}",
    }

    response = await async_client.post("/v1/organizations/", json=data)
    if response.status_code != status.HTTP_201_CREATED:
        print(f"Response: {response.status_code}, Body: {response.json()}")
    assert response.status_code == status.HTTP_201_CREATED

    result = response.json()
    assert result["name"] == data["name"]
    assert result["webhook_email"] == data["webhook_email"]
    assert result["is_active"] is True


async def test_create_organization_duplicate_name(
    async_client: AsyncClient, db_session, setup_db
):
    """Test creating an organization with a duplicate name."""
    unique_id = str(uuid.uuid4()).split("-")[0]
    common_name = f"Duplicate Name Org {unique_id}"

    # Create first organization
    data1 = {
        "name": common_name,
        "webhook_email": f"test1_{unique_id}@example.com",
        "mandrill_api_key": f"test-api-key-1-{unique_id}",
        "mandrill_webhook_secret": f"test-webhook-secret-1-{unique_id}",
    }
    response1 = await async_client.post("/v1/organizations/", json=data1)
    if response1.status_code != status.HTTP_201_CREATED:
        print(f"Response: {response1.status_code}, Body: {response1.json()}")
    assert response1.status_code == status.HTTP_201_CREATED

    # Attempt to create second organization with same name
    data2 = {
        "name": common_name,  # Same name as first org
        "webhook_email": f"test2_{unique_id}@example.com",
        "mandrill_api_key": f"test-api-key-2-{unique_id}",
        "mandrill_webhook_secret": f"test-webhook-secret-2-{unique_id}",
    }
    response2 = await async_client.post("/v1/organizations/", json=data2)
    assert response2.status_code == status.HTTP_409_CONFLICT
    assert "already exists" in response2.json()["detail"]


async def test_create_organization_duplicate_webhook_secret(
    async_client: AsyncClient, db_session, setup_db
):
    """Test creating an organization with a duplicate webhook secret."""
    unique_id = str(uuid.uuid4()).split("-")[0]
    common_secret = f"same-webhook-secret-{unique_id}"

    # Create first organization
    data1 = {
        "name": f"First Org {unique_id}",
        "webhook_email": f"test1_{unique_id}@example.com",
        "mandrill_api_key": f"test-api-key-1-{unique_id}",
        "mandrill_webhook_secret": common_secret,
    }
    response1 = await async_client.post("/v1/organizations/", json=data1)
    if response1.status_code != status.HTTP_201_CREATED:
        print(f"Response: {response1.status_code}, Body: {response1.json()}")
    assert response1.status_code == status.HTTP_201_CREATED

    # Attempt to create second organization with same webhook secret
    data2 = {
        "name": f"Second Org {unique_id}",
        "webhook_email": f"test2_{unique_id}@example.com",
        "mandrill_api_key": f"test-api-key-2-{unique_id}",
        "mandrill_webhook_secret": common_secret,  # Same secret as first org
    }
    response2 = await async_client.post("/v1/organizations/", json=data2)
    assert response2.status_code == status.HTTP_409_CONFLICT
    assert "security risk" in response2.json()["detail"]


async def test_update_organization_duplicate_webhook_secret(
    async_client: AsyncClient, db_session, setup_db
):
    """Test updating an organization with a duplicate webhook secret."""
    unique_id = str(uuid.uuid4()).split("-")[0]
    first_secret = f"first-webhook-secret-{unique_id}"
    second_secret = f"second-webhook-secret-{unique_id}"

    # Create first organization
    data1 = {
        "name": f"First Update Org {unique_id}",
        "webhook_email": f"update1_{unique_id}@example.com",
        "mandrill_api_key": f"update-api-key-1-{unique_id}",
        "mandrill_webhook_secret": first_secret,
    }
    response1 = await async_client.post("/v1/organizations/", json=data1)
    if response1.status_code != status.HTTP_201_CREATED:
        print(f"Response: {response1.status_code}, Body: {response1.json()}")
    assert response1.status_code == status.HTTP_201_CREATED

    # Create second organization
    data2 = {
        "name": f"Second Update Org {unique_id}",
        "webhook_email": f"update2_{unique_id}@example.com",
        "mandrill_api_key": f"update-api-key-2-{unique_id}",
        "mandrill_webhook_secret": second_secret,
    }
    response2 = await async_client.post("/v1/organizations/", json=data2)
    if response2.status_code != status.HTTP_201_CREATED:
        print(f"Response: {response2.status_code}, Body: {response2.json()}")
    assert response2.status_code == status.HTTP_201_CREATED

    # Try to update second organization to use first org's webhook secret
    update_data = {
        "mandrill_webhook_secret": first_secret,  # Use first org's secret
    }
    response3 = await async_client.put(
        f"/v1/organizations/{response2.json()['id']}", json=update_data
    )
    assert response3.status_code == status.HTTP_409_CONFLICT
    assert "security risk" in response3.json()["detail"]


async def test_get_organization(async_client: AsyncClient, db_session, setup_db):
    """Test getting an organization."""
    unique_id = str(uuid.uuid4()).split("-")[0]

    # Create organization
    data = {
        "name": f"Get Test Org {unique_id}",
        "webhook_email": f"get_{unique_id}@example.com",
        "mandrill_api_key": f"get-api-key-{unique_id}",
        "mandrill_webhook_secret": f"get-webhook-secret-{unique_id}",
    }
    response = await async_client.post("/v1/organizations/", json=data)
    if response.status_code != status.HTTP_201_CREATED:
        print(f"Response: {response.status_code}, Body: {response.json()}")
    assert response.status_code == status.HTTP_201_CREATED
    org_id = response.json()["id"]

    # Get organization
    get_response = await async_client.get(f"/v1/organizations/{org_id}")
    assert get_response.status_code == status.HTTP_200_OK
    assert get_response.json()["name"] == data["name"]
    assert get_response.json()["webhook_email"] == data["webhook_email"]
