"""Add AttachmentTextContent model

Revision ID: 1139e0980984
Revises: daf60e35187d
Create Date: 2025-04-22 19:33:08.032575

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1139e0980984"
down_revision: Union[str, None] = "daf60e35187d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to add AttachmentTextContent table."""
    # Create the attachment_text_content table
    op.create_table(
        "attachment_text_content",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("attachment_id", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("text_content", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["attachment_id"],
            ["attachments.id"],
            name="fk_attachment_text_content_attachment_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_attachment_text_content"),
    )

    # Create indexes
    op.create_index(
        "ix_attachment_text_content_id", "attachment_text_content", ["id"], unique=False
    )
    op.create_index(
        "ix_attachment_text_content_attachment_id",
        "attachment_text_content",
        ["attachment_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema to remove AttachmentTextContent table."""
    # Drop the indexes
    op.drop_index(
        "ix_attachment_text_content_attachment_id", table_name="attachment_text_content"
    )
    op.drop_index("ix_attachment_text_content_id", table_name="attachment_text_content")

    # Drop the table
    op.drop_table("attachment_text_content")
