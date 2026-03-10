"""fix file_path format in entries

Revision ID: d3e5f7a9b1c3
Revises: 450fb789f032
Create Date: 2026-02-10 00:10:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d3e5f7a9b1c3"
down_revision: Union[str, None] = "c2d4e6f8a0b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Fix file_path format: convert ':path:type' to just 'path'."""
    # Use raw SQL to update file_path values that have the BibTeX format
    # Pattern: ":path:type" -> extract just "path"
    op.execute("""
        UPDATE entries 
        SET file_path = CASE
            WHEN file_path LIKE ':%:%' THEN
                -- Extract middle part: split on ':', take second element
                SPLIT_PART(file_path, ':', 2)
            ELSE file_path
        END
        WHERE file_path IS NOT NULL AND file_path LIKE ':%';
    """)


def downgrade() -> None:
    """Cannot reliably restore original format."""
    pass
