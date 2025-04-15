"""add_unique_constraint_to_mandrill_webhook_secret

Revision ID: 3d17b3a3f001
Revises: 136d5ef8e384
Create Date: 2025-04-15 16:18:15.242567

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3d17b3a3f001"
down_revision: Union[str, None] = "136d5ef8e384"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
