"""add index to s2_citations target_id

Revision ID: 450fb789f032
Revises: a4abdba27633
Create Date: 2026-01-30 16:00:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "450fb789f032"
down_revision = "a4abdba27633"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_s2_citations_target_id", "s2_citations", ["target_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_s2_citations_target_id", table_name="s2_citations")
