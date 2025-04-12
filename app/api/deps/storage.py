"""Storage dependencies for dependency injection."""

from app.services.storage_service import StorageService

__all__ = ["get_storage_service"]


async def get_storage_service() -> StorageService:
    """Dependency function to get the storage service.

    This dependency provides a service for interacting with file storage,
    which can be either cloud-based (S3) or local filesystem based on the
    application configuration.

    Returns:
        StorageService: The storage service instance configured based on
            application settings

    Example:
        ```python
        @app.get("/files/{file_id}")
        async def get_file(
            file_id: str,
            storage: StorageService = Depends(get_storage_service)
        ) -> Response:
            # Get file from storage using a URI
            file_uri = f"s3://bucket/{file_id}"
            file_data = await storage.get_file(file_uri)

            if not file_data:
                raise HTTPException(status_code=404, detail="File not found")

            return Response(
                content=file_data,
                media_type="application/octet-stream"
            )
        ```
    """
    return StorageService()
