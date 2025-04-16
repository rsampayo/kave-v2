"""add_unique_constraint_to_mandrill_webhook_secret

Revision ID: 7b40d1074b24
Revises: 3d17b3a3f001
Create Date: 2025-04-15 16:18:41.381596

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.exc import OperationalError

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7b40d1074b24"
down_revision: Union[str, None] = "3d17b3a3f001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
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
        except (sa.exc.ProgrammingError, OperationalError):
            # Constraint might already exist
            pass


def downgrade() -> None:
    """Downgrade schema."""
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
        except (sa.exc.ProgrammingError, OperationalError):
            # Constraint might not exist
            pass
