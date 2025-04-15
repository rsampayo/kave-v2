"""add_unique_constraint_to_mandrill_webhook_secret

Revision ID: 7b40d1074b24
Revises: 3d17b3a3f001
Create Date: 2025-04-15 16:18:41.381596

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7b40d1074b24"
down_revision: Union[str, None] = "3d17b3a3f001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_unique_constraint(
        "uq_organizations_mandrill_webhook_secret",
        "organizations",
        ["mandrill_webhook_secret"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "uq_organizations_mandrill_webhook_secret", "organizations", type_="unique"
    )
