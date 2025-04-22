"""add_unique_constraint_to_mandrill_webhook_secret

Revision ID: 7b40d1074b24
Revises: 3d17b3a3f001
Create Date: 2025-04-15 16:18:41.381596

"""

import logging
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.exc import InternalError, OperationalError, ProgrammingError

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7b40d1074b24"
down_revision: Union[str, None] = "3d17b3a3f001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Configure logging
logger = logging.getLogger("alembic")


def upgrade() -> None:
    """Upgrade schema."""
    # NOTE: This migration has been superseded by daf60e35187d which provides
    # a more robust implementation of the same constraint. However, we maintain
    # this migration to preserve the migration chain in existing deployments.

    # Check current dialect
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    dialect = inspector.dialect.name

    # Only apply this migration for PostgreSQL, skip for SQLite
    if dialect == "postgresql":
        try:
            op.create_unique_constraint(
                "uq_organizations_mandrill_webhook_secret",
                "organizations",
                ["mandrill_webhook_secret"],
            )
            logger.info("Created unique constraint for mandrill_webhook_secret")
        except (ProgrammingError, OperationalError, InternalError) as e:
            # Constraint might already exist
            logger.warning(f"Could not create constraint: {str(e)}")


def downgrade() -> None:
    """Downgrade schema."""
    # NOTE: This migration has been superseded by daf60e35187d.
    # However, we maintain this migration to preserve the migration chain.

    # Check current dialect
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    dialect = inspector.dialect.name

    # Only apply this migration for PostgreSQL, skip for SQLite
    if dialect == "postgresql":
        try:
            op.drop_constraint(
                "uq_organizations_mandrill_webhook_secret",
                "organizations",
                type_="unique",
            )
            logger.info("Dropped unique constraint for mandrill_webhook_secret")
        except (ProgrammingError, OperationalError, InternalError) as e:
            # Constraint might not exist
            logger.warning(f"Could not drop constraint: {str(e)}")
