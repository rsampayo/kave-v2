"""add_test_column

Revision ID: 0815edbd2640
Revises: d2c4eb2be839
Create Date: 2025-04-09 11:29:18.082878

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0815edbd2640"
down_revision: Union[str, None] = "d2c4eb2be839"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("emails", sa.Column("test_column", sa.String(100), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("emails", "test_column")
