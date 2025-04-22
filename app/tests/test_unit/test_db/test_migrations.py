"""Unit tests for database migration scripts."""

from typing import Any

# from app.db.migrations.migrate_storage_uri import migrate_existing_attachments
# from app.db.migrations.remove_attachment_content import (
#     upgrade as remove_attachment_content,
# )


# @pytest.mark.asyncio
# async def test_migrate_storage_uri() -> None:
#     """Test that the migrate_storage_uri script correctly uploads content to storage."""
#     # Set up mocks
#     mock_session = AsyncMock()
#
#     # Create test data
#     mock_attachment1 = MagicMock(spec=Attachment)
#     mock_attachment1.id = "attach-1"
#     mock_attachment1.email_id = "email-1"
#     mock_attachment1.filename = "test1.txt"
#     mock_attachment1.content_type = "text/plain"
#     mock_attachment1.content = base64.b64encode(b"test content 1")
#     mock_attachment1.storage_uri = None
#
#     mock_attachment2 = MagicMock(spec=Attachment)
#     mock_attachment2.id = "attach-2"
#     mock_attachment2.email_id = "email-2"
#     mock_attachment2.filename = "test2.txt"
#     mock_attachment2.content_type = "text/plain"
#     mock_attachment2.content = base64.b64encode(b"test content 2")
#     mock_attachment2.storage_uri = None
#
#     # Configure mocks
#     mock_result = MagicMock()
#     mock_result.scalars.return_value.all.return_value = [
#         mock_attachment1,
#         mock_attachment2,
#     ]
#     mock_session.execute.return_value = mock_result
#
#     # Mock the storage service
#     mock_storage = AsyncMock()
#     mock_storage.save_file.side_effect = [
#         "s3://bucket/attachments/email-1/attach-1_test1.txt",
#         "s3://bucket/attachments/email-2/attach-2_test2.txt",
#     ]
#
#     # Create a more controlled mock engine
#     mock_engine = MagicMock()
#     mock_dispose = AsyncMock()
#     # Use PropertyMock for the dispose attribute
#     type(mock_engine).dispose = PropertyMock(return_value=mock_dispose)
#
#     # Patch the necessary dependencies
#     with (
#         patch(
#             "app.db.migrations.migrate_storage_uri.get_session",
#             return_value=mock_session,
#         ),
#         patch("app.db.migrations.migrate_storage_uri.init_db", AsyncMock()),
#         patch(
#             "app.db.migrations.migrate_storage_uri.StorageService",
#             return_value=mock_storage,
#         ),
#         patch("app.db.migrations.migrate_storage_uri.engine", mock_engine),
#     ):
#         # Run the migration
#         await migrate_existing_attachments()
#
#         # Verify the select query was called correctly
#         mock_session.execute.assert_called_once()
#         select_call = mock_session.execute.call_args[0][0]
#         assert isinstance(select_call, Select)
#         # Verify storage service received correct arguments
#         mock_storage.save_file.assert_has_calls(
#             [
#                 call(
#                     file_data=base64.b64encode(b"test content 1"),
#                     object_key="attachments/email-1/attach-1_test1.txt",
#                     content_type="text/plain",
#                 ),
#                 call(
#                     file_data=base64.b64encode(b"test content 2"),
#                     object_key="attachments/email-2/attach-2_test2.txt",
#                     content_type="text/plain",
#                 ),
#             ]
#         )
#         # Verify attachments were updated
#         uri1 = "s3://bucket/attachments/email-1/attach-1_test1.txt"
#         assert mock_attachment1.storage_uri == uri1
#         uri2 = "s3://bucket/attachments/email-2/attach-2_test2.txt"
#         assert mock_attachment2.storage_uri == uri2
#         # Verify the session was committed
#         mock_session.commit.assert_awaited_once()
#         # Verify engine.dispose was called
#         mock_dispose.assert_awaited_once()
#
#
# @pytest.mark.asyncio
# async def test_migrate_storage_uri_with_errors() -> None:
#     """Test that the migrate_storage_uri script handles errors gracefully."""
#     # Set up mocks
#     mock_session = AsyncMock()
#
#     # Create test data
#     mock_attachment1 = MagicMock(spec=Attachment)
#     mock_attachment1.id = "attach-1"
#     mock_attachment1.email_id = "email-1"
#     mock_attachment1.filename = "test1.txt"
#     mock_attachment1.content_type = "text/plain"
#     mock_attachment1.content = base64.b64encode(b"test content 1")
#     mock_attachment1.storage_uri = None
#
#     mock_attachment2 = MagicMock(spec=Attachment)
#     mock_attachment2.id = "attach-2"
#     mock_attachment2.email_id = "email-2"
#     mock_attachment2.filename = "test2.txt"
#     mock_attachment2.content_type = "text/plain"
#     mock_attachment2.content = None  # Missing content should be skipped
#     mock_attachment2.storage_uri = None
#
#     # Configure mocks
#     mock_result = MagicMock()
#     mock_result.scalars.return_value.all.return_value = [
#         mock_attachment1,
#         mock_attachment2,
#     ]
#     mock_session.execute.return_value = mock_result
#
#     # Mock the storage service
#     mock_storage = AsyncMock()
#     mock_storage.save_file.return_value = (
#         "s3://bucket/attachments/email-1/attach-1_test1.txt"
#     )
#
#     # Create a more controlled mock engine
#     mock_engine = MagicMock()
#     mock_dispose = AsyncMock()
#     # Use PropertyMock for the dispose attribute
#     type(mock_engine).dispose = PropertyMock(return_value=mock_dispose)
#
#     # Patch the necessary dependencies
#     with (
#         patch(
#             "app.db.migrations.migrate_storage_uri.get_session",
#             return_value=mock_session,
#         ),
#         patch("app.db.migrations.migrate_storage_uri.init_db", AsyncMock()),
#         patch(
#             "app.db.migrations.migrate_storage_uri.StorageService",
#             return_value=mock_storage,
#         ),
#         patch("app.db.migrations.migrate_storage_uri.engine", mock_engine),
#     ):
#         # Run the migration
#         await migrate_existing_attachments()
#
#         # Verify the save_file method was called only for the valid attachment
#         assert mock_storage.save_file.call_count == 1
#         # Verify the storage_uri was updated only for the valid attachment
#         uri = "s3://bucket/attachments/email-1/attach-1_test1.txt"
#         assert mock_attachment1.storage_uri == uri
#         assert mock_attachment2.storage_uri is None  # Should remain None
#         # Verify the session was committed
#         mock_session.commit.assert_awaited_once()
#         # Verify engine.dispose was called
#         mock_dispose.assert_awaited_once()


class AsyncContextManagerMock:
    """A mock class for async context managers."""

    def __init__(self, mock_obj: Any) -> None:
        self.mock_obj = mock_obj

    async def __aenter__(self) -> Any:
        return self.mock_obj

    async def __aexit__(
        self, exc_type: type | None, exc_val: Exception | None, exc_tb: Any
    ) -> None:
        pass


# @pytest.mark.asyncio
# async def test_remove_attachment_content() -> None:
#     """Test that the remove_attachment_content script handles column nullability.
#
#     Checks PostgreSQL behavior.
#     """
#     # Create a proper AsyncEngine mock with a working context manager
#     mock_engine = MagicMock(spec=AsyncEngine)
#     mock_conn = AsyncMock()
#
#     # Set up the connect method to return our async context manager
#     mock_engine.connect.return_value = AsyncContextManagerMock(mock_conn)
#
#     # Set dialect name
#     mock_engine.dialect = MagicMock()
#     mock_engine.dialect.name = "postgresql"
#
#     # Mock the query execution
#     mock_result = MagicMock()
#     mock_conn.execute.return_value = mock_result
#
#     # Run the migration with our properly mocked engine
#     await remove_attachment_content(mock_engine)
#
#     # Verify the SQL execution was performed correctly
#     mock_conn.execute.assert_called_once()
#     # Verify the statement was committed
#     mock_conn.commit.assert_awaited_once()
#
#
# @pytest.mark.asyncio
# async def test_remove_attachment_content_sqlite() -> None:
#     """Test that the remove_attachment_content script handles SQLite dialect.
#
#     Verifies SQLite-specific behavior.
#     """
#     # Create a proper AsyncEngine mock with a working context manager
#     mock_engine = MagicMock(spec=AsyncEngine)
#     mock_conn = AsyncMock()
#
#     # Set up the connect method to return our async context manager
#     mock_engine.connect.return_value = AsyncContextManagerMock(mock_conn)
#
#     # Set dialect name to sqlite
#     mock_engine.dialect = MagicMock()
#     mock_engine.dialect.name = "sqlite"
#
#     # Mock SQLite PRAGMA response: column_id, name, type, notnull, default, pk
#     # notnull=0 means nullable
#     mock_columns = [(1, "content", "BLOB", 0, None, 0)]
#     mock_result = MagicMock()
#     mock_result.fetchall.return_value = mock_columns
#     mock_conn.execute.return_value = mock_result
#
#     # Run the migration with our properly mocked engine
#     await remove_attachment_content(mock_engine)
