"""Module providing Attachments functionality for the api endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_storage_service
from app.models.email_data import Attachment
from app.services.storage_service import StorageService

router = APIRouter()


@router.get(
    "/{attachment_id}",
    summary="Download attachment",
    description=(
        "Download an email attachment by its ID. "
        "Retrieves attachment from cloud storage or database."
    ),
)
async def get_attachment(
    attachment_id: int,
    db: AsyncSession = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
) -> Response:
    """Get an attachment file by ID.

    Args:
        attachment_id: The ID of the attachment
        db: Database session
        storage: Storage service

    Returns:
        Response: The attachment file content

    Raises:
        HTTPException: If attachment not found or content unavailable
    """
    # Query for the attachment by ID
    result = await db.execute(select(Attachment).where(Attachment.id == attachment_id))
    attachment = result.scalar_one_or_none()

    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")

    # Try to get content from storage_uri first
    file_data = None
    if attachment.storage_uri:
        file_data = await storage.get_file(attachment.storage_uri)

    # Fall back to database content if storage_uri doesn't work
    if not file_data and attachment.content:
        file_data = attachment.content

    if not file_data:
        raise HTTPException(status_code=404, detail="Attachment content not available")

    # Return the file as a response with the correct content type
    return Response(
        content=file_data,
        media_type=attachment.content_type,
        headers={
            "Content-Disposition": f"attachment; filename={attachment.filename!r}"
        },
    )
