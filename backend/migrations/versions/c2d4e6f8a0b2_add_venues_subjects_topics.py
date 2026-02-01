"""Add venues, subjects, topics tables and relations

Revision ID: c2d4e6f8a0b2
Revises: 450fb789f032
Create Date: 2026-02-01 22:55:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c2d4e6f8a0b2"
down_revision: Union[str, None] = "450fb789f032"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create venue_category enum using raw SQL for idempotent creation
    # (checkfirst doesn't work reliably with asyncpg)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE venue_category AS ENUM ('CONFERENCE', 'JOURNAL');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    # Create venues table
    op.create_table(
        "venues",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("slug", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "category",
            postgresql.ENUM(
                "CONFERENCE", "JOURNAL", name="venue_category", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("aliases", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index(op.f("ix_venues_slug"), "venues", ["slug"], unique=True)

    # Create subjects table
    op.create_table(
        "subjects",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index(op.f("ix_subjects_slug"), "subjects", ["slug"], unique=True)

    # Create topics table
    op.create_table(
        "topics",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index(op.f("ix_topics_slug"), "topics", ["slug"], unique=True)

    # Add venue_id and subject_id to entries table
    op.add_column(
        "entries",
        sa.Column("venue_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "entries",
        sa.Column("subject_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_entries_venue_id",
        "entries",
        "venues",
        ["venue_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_entries_subject_id",
        "entries",
        "subjects",
        ["subject_id"],
        ["id"],
    )
    op.create_index(op.f("ix_entries_venue_id"), "entries", ["venue_id"], unique=False)
    op.create_index(
        op.f("ix_entries_subject_id"), "entries", ["subject_id"], unique=False
    )

    # Create entry_topics junction table
    op.create_table(
        "entry_topics",
        sa.Column("entry_id", sa.UUID(), nullable=False),
        sa.Column("topic_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["entry_id"], ["entries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["topic_id"], ["topics.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("entry_id", "topic_id"),
    )


def downgrade() -> None:
    # Drop entry_topics junction table
    op.drop_table("entry_topics")

    # Drop foreign keys and columns from entries
    op.drop_index(op.f("ix_entries_subject_id"), table_name="entries")
    op.drop_index(op.f("ix_entries_venue_id"), table_name="entries")
    op.drop_constraint("fk_entries_subject_id", "entries", type_="foreignkey")
    op.drop_constraint("fk_entries_venue_id", "entries", type_="foreignkey")
    op.drop_column("entries", "subject_id")
    op.drop_column("entries", "venue_id")

    # Drop topics table
    op.drop_index(op.f("ix_topics_slug"), table_name="topics")
    op.drop_table("topics")

    # Drop subjects table
    op.drop_index(op.f("ix_subjects_slug"), table_name="subjects")
    op.drop_table("subjects")

    # Drop venues table
    op.drop_index(op.f("ix_venues_slug"), table_name="venues")
    op.drop_table("venues")

    # Drop venue_category enum
    sa.Enum(name="venue_category").drop(op.get_bind(), checkfirst=True)
