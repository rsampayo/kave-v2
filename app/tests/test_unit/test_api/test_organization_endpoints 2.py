"""Tests for organization endpoints."""

import uuid
from unittest import mock
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException, status
from httpx import AsyncClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.organizations import (
    delete_organization,
    patch_organization,
    update_organization,
)
from app.models.organization import Organization
from app.models.user import User
from app.schemas.organization_schemas import OrganizationUpdate

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
    async_client: AsyncClient, db_session: AsyncSession, monkeypatch
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

    # Create a mock commit method that raises an IntegrityError with appropriate message
    async def mock_commit(self):
        error = IntegrityError(
            statement="INSERT INTO organizations ...",
            params={},
            orig=Exception(
                "duplicate key value violates unique constraint "
                '"uq_organizations_mandrill_webhook_secret"'
            ),
        )
        raise error

    # Patch the commit method with our mock
    with mock.patch("sqlalchemy.ext.asyncio.AsyncSession.commit", mock_commit):
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
    async_client: AsyncClient, db_session: AsyncSession, monkeypatch
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

    # Create a mock commit method that raises an IntegrityError with appropriate message
    async def mock_commit(self):
        error = IntegrityError(
            statement="UPDATE organizations SET mandrill_webhook_secret=... WHERE id=...",
            params={},
            orig=Exception(
                "duplicate key value violates unique constraint "
                '"uq_organizations_mandrill_webhook_secret"'
            ),
        )
        raise error

    # Patch the commit method with our mock
    with mock.patch("sqlalchemy.ext.asyncio.AsyncSession.commit", mock_commit):
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

    # Create a few test organizations
    orgs_data = [
        {
            "name": f"List Org 1 {unique_id}",
            "webhook_email": f"list1_{unique_id}@example.com",
            "mandrill_api_key": f"list-api-key-1-{unique_id}",
            "mandrill_webhook_secret": f"list-webhook-secret-1-{unique_id}",
        },
        {
            "name": f"List Org 2 {unique_id}",
            "webhook_email": f"list2_{unique_id}@example.com",
            "mandrill_api_key": f"list-api-key-2-{unique_id}",
            "mandrill_webhook_secret": f"list-webhook-secret-2-{unique_id}",
        },
    ]

    for data in orgs_data:
        response = await async_client.post("/v1/organizations/", json=data)
        assert response.status_code == status.HTTP_201_CREATED

    # Retrieve all organizations
    list_response = await async_client.get("/v1/organizations/")
    assert list_response.status_code == status.HTTP_200_OK

    # Verify our test orgs are in the list
    response_data = list_response.json()
    assert isinstance(response_data, list)
    assert len(response_data) >= 2  # At least our two test orgs
    org_names = [org["name"] for org in response_data]
    for data in orgs_data:
        assert data["name"] in org_names


@pytest.mark.asyncio
async def test_update_organization_not_found():
    """Test updating an organization that doesn't exist."""
    # Arrange
    mock_user = User(id=1, username="admin", is_active=True, is_superuser=True)
    mock_db = AsyncMock()
    mock_service = AsyncMock()
    mock_service.get_organization_by_id.return_value = None

    # Create update data
    data = OrganizationUpdate(name="Updated Name")

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await update_organization(99, data, mock_db, mock_service, mock_user)

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    assert "not found" in exc_info.value.detail
    mock_service.update_organization.assert_not_awaited()
    mock_db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_organization_duplicate_name():
    """Test updating an organization with a name that conflicts with an existing one."""
    # Arrange
    existing_org = Organization(id=1, name="Org 1", webhook_email="org1@example.com")
    another_org = Organization(id=2, name="Org 2", webhook_email="org2@example.com")

    mock_user = User(id=1, username="admin", is_active=True, is_superuser=True)
    mock_db = AsyncMock()
    mock_service = AsyncMock()
    mock_service.get_organization_by_id.return_value = existing_org
    mock_service.get_organization_by_name.return_value = another_org

    # Create update data with name that already exists
    data = OrganizationUpdate(name="Org 2")

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await update_organization(1, data, mock_db, mock_service, mock_user)

    assert exc_info.value.status_code == status.HTTP_409_CONFLICT
    assert "already exists" in exc_info.value.detail
    mock_service.update_organization.assert_not_awaited()
    mock_db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_organization_duplicate_email():
    """Test updating an organization with an email that conflicts with an existing one."""
    # Arrange
    existing_org = Organization(id=1, name="Org 1", webhook_email="org1@example.com")
    another_org = Organization(id=2, name="Org 2", webhook_email="org2@example.com")

    mock_user = User(id=1, username="admin", is_active=True, is_superuser=True)
    mock_db = AsyncMock()
    mock_service = AsyncMock()
    mock_service.get_organization_by_id.return_value = existing_org
    mock_service.get_organization_by_name.return_value = None
    mock_service.get_organization_by_email.return_value = another_org

    # Create update data with email that already exists
    data = OrganizationUpdate(name="Org 1 Updated", webhook_email="org2@example.com")

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await update_organization(1, data, mock_db, mock_service, mock_user)

    assert exc_info.value.status_code == status.HTTP_409_CONFLICT
    assert "already exists" in exc_info.value.detail
    mock_service.update_organization.assert_not_awaited()
    mock_db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_patch_organization_not_found():
    """Test patching an organization that doesn't exist."""
    # Arrange
    mock_user = User(id=1, username="admin", is_active=True, is_superuser=True)
    mock_db = AsyncMock()
    mock_service = AsyncMock()
    mock_service.get_organization_by_id.return_value = None

    # Create patch data
    data = OrganizationUpdate(description="Updated description")

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await patch_organization(99, data, mock_db, mock_service, mock_user)

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    assert "not found" in exc_info.value.detail
    mock_service.update_organization.assert_not_awaited()
    mock_db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_organization_success() -> None:
    """Test successful organization deletion."""
    # Arrange
    existing_org = Organization(id=1, name="Org 1", webhook_email="org1@example.com")

    mock_user = User(id=1, username="admin", is_active=True, is_superuser=True)
    mock_db = AsyncMock()
    mock_service = AsyncMock()
    mock_service.get_organization_by_id.return_value = existing_org
    mock_service.delete_organization.return_value = None

    # Act
    await delete_organization(1, mock_db, mock_service, mock_user)

    # Assert
    mock_service.get_organization_by_id.assert_awaited_once_with(1)
    mock_service.delete_organization.assert_awaited_once_with(1)
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_organization_not_found() -> None:
    """Test deleting an organization that doesn't exist."""
    # Arrange
    mock_user = User(id=1, username="admin", is_active=True, is_superuser=True)
    mock_db = AsyncMock()
    mock_service = AsyncMock()
    mock_service.get_organization_by_id.return_value = None

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await delete_organization(99, mock_db, mock_service, mock_user)

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    assert "not found" in exc_info.value.detail
    mock_service.delete_organization.assert_not_awaited()
    mock_db.commit.assert_not_awaited()
