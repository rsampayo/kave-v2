"""fix_unique_constraint_for_postgres

Revision ID: daf60e35187d
Revises: 443a8e83492a
Create Date: 2025-04-16 09:19:43.413577

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.engine import reflection
from sqlalchemy.exc import InternalError, OperationalError, ProgrammingError

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "daf60e35187d"
down_revision: Union[str, None] = "443a8e83492a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema with PostgreSQL compatibility."""
    # Check if we're using PostgreSQL
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    dialect = inspector.dialect.name

    if dialect == "postgresql":
        # Check if the table and column exist before adding constraints
        insp = reflection.Inspector.from_engine(conn)
        if "organizations" in insp.get_table_names() and "mandrill_webhook_secret" in [
            col["name"] for col in insp.get_columns("organizations")
        ]:

            # Check if constraint already exists
            constraints = insp.get_unique_constraints("organizations")
            constraint_names = [constraint["name"] for constraint in constraints]

            if "uq_organizations_mandrill_webhook_secret" not in constraint_names:
                try:
                    op.create_unique_constraint(
                        "uq_organizations_mandrill_webhook_secret",
                        "organizations",
                        ["mandrill_webhook_secret"],
                    )
                except (ProgrammingError, OperationalError, InternalError) as e:
                    # Log the error but continue
                    print(f"Warning: Could not create constraint: {str(e)}")
                    # Commit what we've done so far to avoid transaction interruption
                    conn.execute(sa.text("COMMIT"))


def downgrade() -> None:
    """Downgrade schema with PostgreSQL compatibility."""
    # Check if we're using PostgreSQL
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    dialect = inspector.dialect.name

    if dialect == "postgresql":
        # Check if constraint exists before trying to drop it
        insp = reflection.Inspector.from_engine(conn)
        constraints = insp.get_unique_constraints("organizations")
        constraint_names = [constraint["name"] for constraint in constraints]

        if "uq_organizations_mandrill_webhook_secret" in constraint_names:
            try:
                op.drop_constraint(
                    "uq_organizations_mandrill_webhook_secret",
                    "organizations",
                    type_="unique",
                )
            except (ProgrammingError, OperationalError, InternalError) as e:
                # Log the error but continue
                print(f"Warning: Could not drop constraint: {str(e)}")
                # Commit what we've done so far to avoid transaction interruption
                conn.execute(sa.text("COMMIT"))
