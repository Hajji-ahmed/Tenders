"""tender normalized fields (norm_title, norm_org, norm_reference)

Revision ID: 8d2e3f4a5b6c
Revises: 7c1d2e3f4a5b
Create Date: 2026-09-15 10:00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8d2e3f4a5b6c"
down_revision: Union[str, Sequence[str], None] = "7c1d2e3f4a5b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("tenders", sa.Column("norm_title", sa.String(length=512), nullable=True))
    op.add_column("tenders", sa.Column("norm_org", sa.String(length=255), nullable=True))
    op.add_column("tenders", sa.Column("norm_reference", sa.String(length=128), nullable=True))
    op.create_index(op.f("ix_tenders_norm_org"), "tenders", ["norm_org"], unique=False)
    op.create_index(op.f("ix_tenders_norm_reference"), "tenders", ["norm_reference"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_tenders_norm_reference"), table_name="tenders")
    op.drop_index(op.f("ix_tenders_norm_org"), table_name="tenders")
    op.drop_column("tenders", "norm_reference")
    op.drop_column("tenders", "norm_org")
    op.drop_column("tenders", "norm_title")
