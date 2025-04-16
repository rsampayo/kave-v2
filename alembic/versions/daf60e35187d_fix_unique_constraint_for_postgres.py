"""fix_unique_constraint_for_postgres

Revision ID: daf60e35187d
Revises: 7b40d1074b24
Create Date: 2025-04-16 09:19:43.413577

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import OperationalError


# revision identifiers, used by Alembic.
revision: str = 'daf60e35187d'
down_revision: Union[str, None] = '7b40d1074b24'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema with PostgreSQL compatibility."""
    # Check if we're using PostgreSQL
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    dialect = inspector.dialect.name
    
    if dialect == "postgresql":
        # For PostgreSQL, apply the constraint directly
        try:
            op.create_unique_constraint(
                "uq_organizations_mandrill_webhook_secret",
                "organizations",
                ["mandrill_webhook_secret"],
            )
        except (sa.exc.ProgrammingError, OperationalError):
            # Constraint might already exist, so we'll ignore the error
            pass


def downgrade() -> None:
    """Downgrade schema with PostgreSQL compatibility."""
    # Check if we're using PostgreSQL
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    dialect = inspector.dialect.name
    
    if dialect == "postgresql":
        try:
            op.drop_constraint(
                "uq_organizations_mandrill_webhook_secret", 
                "organizations", 
                type_="unique"
            )
        except (sa.exc.ProgrammingError, OperationalError):
            # If constraint doesn't exist, ignore the error
            pass
