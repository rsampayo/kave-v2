"""test_alembic_functionality

Revision ID: 9388bd8f46d0
Revises: 0815edbd2640
Create Date: 2025-04-09 20:41:25.675210

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9388bd8f46d0"
down_revision: Union[str, None] = "0815edbd2640"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add a second test column to emails table
    op.add_column("emails", sa.Column("test_column_two", sa.String(100), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove the second test column
    op.drop_column("emails", "test_column_two")
