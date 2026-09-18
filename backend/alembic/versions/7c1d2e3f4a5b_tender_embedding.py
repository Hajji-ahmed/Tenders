"""tender embedding (pgvector) + index HNSW cosinus

Revision ID: 7c1d2e3f4a5b
Revises: 562b49ff3fda
Create Date: 2026-09-15 09:00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "7c1d2e3f4a5b"
down_revision: Union[str, Sequence[str], None] = "562b49ff3fda"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.add_column("tenders", sa.Column("embedding", Vector(dim=1536), nullable=True))
    op.create_index(
        "ix_tenders_embedding_hnsw",
        "tenders",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_tenders_embedding_hnsw", table_name="tenders", postgresql_using="hnsw")
    op.drop_column("tenders", "embedding")
