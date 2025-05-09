"""Add Organization model

Revision ID: 136d5ef8e384
Revises: 9388bd8f46d0
Create Date: 2025-04-14 18:08:46.273902

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op
from alembic.operations import ops

# revision identifiers, used by Alembic.
revision: str = "136d5ef8e384"
down_revision: Union[str, None] = "9388bd8f46d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    # Create organizations table
    op.create_table(
        "organizations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("webhook_email", sa.String(length=255), nullable=False),
        sa.Column("mandrill_api_key", sa.String(length=255), nullable=False),
        sa.Column("mandrill_webhook_secret", sa.String(length=255), nullable=False),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_organizations_id"), "organizations", ["id"], unique=False)
    op.create_index(
        op.f("ix_organizations_name"), "organizations", ["name"], unique=True
    )
    op.create_index(
        op.f("ix_organizations_webhook_email"),
        "organizations",
        ["webhook_email"],
        unique=False,
    )

    # Add organization_id column to emails table using batch mode for SQLite
    # Get the dialect object to check if we're using SQLite
    context = op.get_context()
    if context.dialect.name == "sqlite":
        # SQLite doesn't support ALTER TABLE ADD FOREIGN KEY
        # so we need to use batch mode to recreate the table
        with op.batch_alter_table("emails") as batch_op:
            batch_op.add_column(
                sa.Column("organization_id", sa.Integer(), nullable=True)
            )
            batch_op.create_index(
                op.f("ix_emails_organization_id"), ["organization_id"], unique=False
            )
            batch_op.create_foreign_key(
                "fk_emails_organization_id",
                "organizations",
                ["organization_id"],
                ["id"],
                ondelete="SET NULL",
            )
    else:
        # For other databases, we can use normal operations
        op.add_column(
            "emails", sa.Column("organization_id", sa.Integer(), nullable=True)
        )
        op.create_index(
            op.f("ix_emails_organization_id"),
            "emails",
            ["organization_id"],
            unique=False,
        )
        op.create_foreign_key(
            "fk_emails_organization_id",
            "emails",
            "organizations",
            ["organization_id"],
            ["id"],
            ondelete="SET NULL",
        )
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    # Remove foreign key constraint from emails table using batch mode for SQLite
    context = op.get_context()
    if context.dialect.name == "sqlite":
        with op.batch_alter_table("emails") as batch_op:
            batch_op.drop_constraint("fk_emails_organization_id", type_="foreignkey")
            batch_op.drop_index(op.f("ix_emails_organization_id"))
            batch_op.drop_column("organization_id")
    else:
        op.drop_constraint("fk_emails_organization_id", "emails", type_="foreignkey")
        op.drop_index(op.f("ix_emails_organization_id"), table_name="emails")
        op.drop_column("emails", "organization_id")

    # Drop organizations table
    op.drop_index(op.f("ix_organizations_webhook_email"), table_name="organizations")
    op.drop_index(op.f("ix_organizations_name"), table_name="organizations")
    op.drop_index(op.f("ix_organizations_id"), table_name="organizations")
    op.drop_table("organizations")
    # ### end Alembic commands ###
