"""Tests for organization endpoints."""

import uuid

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.asyncio


@pytest.mark.asyncio
async def test_create_organization(async_client: AsyncClient, db_session: AsyncSession):
    """Test creating a new organization."""
    # Use a unique identifier to avoid conflicts
    unique_id = str(uuid.uuid4()).split("-")[0]
    data = {
        "name": f"Test Org {unique_id}",
        "webhook_email": f"test_{unique_id}@example.com",
        "mandrill_api_key": f"test-api-key-{unique_id}",
        "mandrill_webhook_secret": f"test-webhook-secret-{unique_id}",
    }

    response = await async_client.post("/v1/organizations/", json=data)
    assert response.status_code == status.HTTP_201_CREATED
    assert "id" in response.json()
    assert response.json()["name"] == data["name"]


@pytest.mark.asyncio
async def test_create_organization_duplicate_name(
    async_client: AsyncClient, db_session: AsyncSession
):
    """Test creating a new organization with a duplicate name."""
    # Use a common name for both organizations to test duplicate handling
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
    assert response1.status_code == status.HTTP_201_CREATED

    # Attempt to create second organization with same name
    data2 = {
        "name": common_name,  # Same name as first org
        "webhook_email": f"test2_{unique_id}@example.com",
        "mandrill_api_key": f"test-api-key-2-{unique_id}",
        "mandrill_webhook_secret": f"test-webhook-secret-2-{unique_id}",
    }
    response2 = await async_client.post("/v1/organizations/", json=data2)

    # Expect a conflict response
    assert response2.status_code == status.HTTP_409_CONFLICT
    assert "already exists" in response2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_organization_duplicate_webhook_secret(
    async_client: AsyncClient, db_session: AsyncSession
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
    assert response1.status_code == status.HTTP_201_CREATED

    # Create second organization with same webhook secret
    data2 = {
        "name": f"Second Org {unique_id}",
        "webhook_email": f"test2_{unique_id}@example.com",
        "mandrill_api_key": f"test-api-key-2-{unique_id}",
        "mandrill_webhook_secret": common_secret,  # Same secret
    }
    response2 = await async_client.post("/v1/organizations/", json=data2)

    # Expect a conflict response for duplicate webhook secret
    assert response2.status_code == status.HTTP_409_CONFLICT
    assert "webhook secret" in response2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_update_organization_duplicate_webhook_secret(
    async_client: AsyncClient, db_session: AsyncSession
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
    assert response1.status_code == status.HTTP_201_CREATED
    org1_id = response1.json()["id"]

    # Create second organization
    data2 = {
        "name": f"Second Update Org {unique_id}",
        "webhook_email": f"update2_{unique_id}@example.com",
        "mandrill_api_key": f"update-api-key-2-{unique_id}",
        "mandrill_webhook_secret": second_secret,
    }
    response2 = await async_client.post("/v1/organizations/", json=data2)
    assert response2.status_code == status.HTTP_201_CREATED

    # Try to update the first organization to use the second org's secret
    update_data = {"mandrill_webhook_secret": second_secret}
    response3 = await async_client.patch(
        f"/v1/organizations/{org1_id}", json=update_data
    )

    # Expect a conflict response
    assert response3.status_code == status.HTTP_409_CONFLICT
    assert "webhook secret" in response3.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_organization(async_client: AsyncClient, db_session: AsyncSession):
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
    assert response.status_code == status.HTTP_201_CREATED
    org_id = response.json()["id"]

    # Retrieve the organization
    get_response = await async_client.get(f"/v1/organizations/{org_id}")
    assert get_response.status_code == status.HTTP_200_OK
    assert get_response.json()["id"] == org_id
    assert get_response.json()["name"] == data["name"]


@pytest.mark.asyncio
async def test_get_nonexistent_organization(
    async_client: AsyncClient, db_session: AsyncSession
):
    """Test getting a non-existent organization."""
    # Generate a random UUID
    non_existent_id = str(uuid.uuid4())

    # Try to get a non-existent organization
    response = await async_client.get(f"/v1/organizations/{non_existent_id}")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_update_organization(async_client: AsyncClient, db_session: AsyncSession):
    """Test updating an organization."""
    unique_id = str(uuid.uuid4()).split("-")[0]

    # Create organization
    data = {
        "name": f"Update Test Org {unique_id}",
        "webhook_email": f"update-test_{unique_id}@example.com",
        "mandrill_api_key": f"update-test-api-key-{unique_id}",
        "mandrill_webhook_secret": f"update-test-webhook-secret-{unique_id}",
    }
    response = await async_client.post("/v1/organizations/", json=data)
    assert response.status_code == status.HTTP_201_CREATED
    org_id = response.json()["id"]

    # Update organization
    update_data = {
        "name": f"Updated Org {unique_id}",
        "webhook_email": f"updated_{unique_id}@example.com",
    }
    update_response = await async_client.put(
        f"/v1/organizations/{org_id}", json=update_data
    )
    assert update_response.status_code == status.HTTP_200_OK
    assert update_response.json()["name"] == update_data["name"]
    assert update_response.json()["webhook_email"] == update_data["webhook_email"]

    # Verify all original fields are preserved (not in update_data)
    assert update_response.json()["mandrill_api_key"] == data["mandrill_api_key"]
    assert (
        update_response.json()["mandrill_webhook_secret"]
        == data["mandrill_webhook_secret"]
    )


@pytest.mark.asyncio
async def test_delete_organization(async_client: AsyncClient, db_session: AsyncSession):
    """Test deleting an organization."""
    unique_id = str(uuid.uuid4()).split("-")[0]

    # Create organization
    data = {
        "name": f"Delete Test Org {unique_id}",
        "webhook_email": f"delete_{unique_id}@example.com",
        "mandrill_api_key": f"delete-api-key-{unique_id}",
        "mandrill_webhook_secret": f"delete-webhook-secret-{unique_id}",
    }
    response = await async_client.post("/v1/organizations/", json=data)
    assert response.status_code == status.HTTP_201_CREATED
    org_id = response.json()["id"]

    # Delete the organization
    delete_response = await async_client.delete(f"/v1/organizations/{org_id}")
    assert delete_response.status_code == status.HTTP_204_NO_CONTENT

    # Verify it's gone
    get_response = await async_client.get(f"/v1/organizations/{org_id}")
    assert get_response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_list_organizations(async_client: AsyncClient, db_session: AsyncSession):
    """Test listing organizations."""
    unique_id = str(uuid.uuid4()).split("-")[0]

    # Create a few organizations
    orgs_data = []
    for i in range(3):
        data = {
            "name": f"List Test Org {i} {unique_id}",
            "webhook_email": f"list{i}_{unique_id}@example.com",
            "mandrill_api_key": f"list-api-key-{i}-{unique_id}",
            "mandrill_webhook_secret": f"list-webhook-secret-{i}-{unique_id}",
        }
        orgs_data.append(data)
        response = await async_client.post("/v1/organizations/", json=data)
        assert response.status_code == status.HTTP_201_CREATED

    # List all organizations
    list_response = await async_client.get("/v1/organizations/")
    assert list_response.status_code == status.HTTP_200_OK

    # Verify our organizations are in the list
    response_data = list_response.json()
    org_names = [org["name"] for org in response_data]
    for data in orgs_data:
        assert data["name"] in org_names
