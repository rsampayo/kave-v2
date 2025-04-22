"""add_unique_constraint_to_mandrill_webhook_secret

Revision ID: 3d17b3a3f001
Revises: 136d5ef8e384
Create Date: 2025-04-15 16:18:15.242567

"""

import logging
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3d17b3a3f001"
down_revision: Union[str, None] = "136d5ef8e384"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Configure logging
logger = logging.getLogger("alembic")


def upgrade() -> None:
    """Upgrade schema."""
    # OBSOLETE MIGRATION: This migration is empty and was superseded by migration daf60e35187d
    # which properly implements the unique constraint for PostgreSQL.
    # We maintain this empty migration to preserve the migration chain in existing deployments.
    logger.info("Skipping obsolete migration 3d17b3a3f001 - superseded by daf60e35187d")
    pass


def downgrade() -> None:
    """Downgrade schema."""
    # OBSOLETE MIGRATION: This migration is empty and was superseded by migration daf60e35187d
    # We maintain this empty migration to preserve the migration chain in existing deployments.
    logger.info("Skipping obsolete migration 3d17b3a3f001 - superseded by daf60e35187d")
    pass
