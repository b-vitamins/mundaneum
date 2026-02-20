"""Add hierarchical subject fields

Revision ID: e4f5g6h7i8j9
Revises: d3e5f7a9b1c3
Create Date: 2026-02-10

Adds parent_slug and display_name to subjects table for hierarchical categorization.
"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "e4f5g6h7i8j9"
down_revision = "d3e5f7a9b1c3"
branch_labels = None
depends_on = None


# --- Inline copies of parser mappings for data migration ---

SUBJECT_PREFIXES = {
    "phy": "Physics",
    "cs": "Computer Science",
    "math": "Mathematics",
    "prog": "Programming",
    "stat": "Statistics",
    "bio": "Biology",
    "biology": "Biology",
    "chem": "Chemistry",
    "econ": "Economics",
    "eng": "Engineering",
    "neuro": "Neuroscience",
    "phil": "Philosophy",
}

FULL_SLUG_SUBJECTS = {
    "popular-science": "Popular Science",
    "science-fiction": "Science Fiction",
    "science-history": "History of Science",
    "self-help": "Self Help",
    "design": "Design",
    "engineering": "Engineering",
    "environment": "Environment",
    "philosophy": "Philosophy",
    "psychology": "Psychology",
    "writing": "Writing",
    "biology": "Biology",
}

CONTEXT_SUBAREA_NAMES = {
    "phy:general": "General Relativity",
    "phy:quantum": "Quantum Mechanics",
    "phy:statistical": "Statistical Mechanics",
    "phy:mathematical": "Mathematical Physics",
    "cs:general": "General",
    "cs:quantum": "Quantum Computing",
    "cs:os": "Operating Systems",
    "math:general": "General",
    "math:statistics": "Statistics",
    "prog:general": "General",
    "prog:design": "Software Design",
    "prog:languages": "Programming Languages",
}

SUBAREA_NAMES = {
    "ml": "Machine Learning",
    "ai": "Artificial Intelligence",
    "ml-ai": "Machine Learning & AI",
    "architecture": "Computer Architecture",
    "vision": "Computer Vision",
    "nlp": "Natural Language Processing",
    "databases": "Databases",
    "systems": "Systems",
    "classical": "Classical Mechanics",
    "field-theory": "Field Theory",
    "electrodynamics": "Electrodynamics",
    "thermodynamics": "Thermodynamics",
    "relativity": "Relativity",
    "analysis": "Analysis",
    "geometry": "Geometry",
    "information-theory": "Information Theory",
    "probability": "Probability",
    "neuroscience": "Neuroscience",
    "algorithms": "Algorithms",
    "functional": "Functional Programming",
    "compilers": "Compilers",
}


def _parse_subject(slug):
    """Parse slug into (parent_slug, display_name, full_name)."""
    if slug in FULL_SLUG_SUBJECTS:
        name = FULL_SLUG_SUBJECTS[slug]
        return slug, name, name

    parts = slug.split("-", 1)
    prefix = parts[0].lower()
    parent = SUBJECT_PREFIXES.get(prefix)

    if parent is None:
        name = slug.replace("-", " ").replace("_", " ").title()
        return slug, name, name

    parent_slug = parent.lower().replace(" ", "-")

    if len(parts) == 1:
        return parent_slug, parent, parent

    subarea_slug = parts[1]
    context_key = f"{prefix}:{subarea_slug}"
    subarea = (
        CONTEXT_SUBAREA_NAMES.get(context_key)
        or SUBAREA_NAMES.get(subarea_slug)
        or subarea_slug.replace("-", " ").title()
    )
    return parent_slug, subarea, f"{parent}: {subarea}"


def upgrade() -> None:
    """Add parent_slug and display_name columns, then populate from existing slugs."""
    op.add_column(
        "subjects",
        sa.Column("parent_slug", sa.String(50), nullable=True, index=True),
    )
    op.add_column(
        "subjects",
        sa.Column("display_name", sa.String(255), nullable=True),
    )

    # Populate data from existing slugs
    conn = op.get_bind()
    subjects = conn.execute(sa.text("SELECT id, slug FROM subjects")).fetchall()

    for subject_id, slug in subjects:
        parent_slug, display_name, full_name = _parse_subject(slug)

        conn.execute(
            sa.text("""
                UPDATE subjects
                SET parent_slug = :parent_slug,
                    display_name = :display_name,
                    name = :name
                WHERE id = :id
            """),
            {
                "parent_slug": parent_slug,
                "display_name": display_name,
                "name": full_name,
                "id": subject_id,
            },
        )


def downgrade() -> None:
    """Remove parent_slug and display_name columns."""
    op.drop_column("subjects", "display_name")
    op.drop_column("subjects", "parent_slug")
