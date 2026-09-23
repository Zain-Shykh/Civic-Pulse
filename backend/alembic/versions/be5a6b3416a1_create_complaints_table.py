"""create complaints table

Revision ID: be5a6b3416a1
Revises:
Create Date: 2026-09-19 19:24:51.901318

Schema exactly per docs/CONTRACTS.md (§2.3) / docs/architecture/SCHEMA.md —
one table, three Postgres native enums, two required indexes. No
speculative columns or tables added.

DB-level length enforcement: CONTRACTS.md says `text` is "10-2000 chars,
enforced in the DB as well as the app" -> explicit CHECK constraint below.
`location`'s note ("3-200 chars") does not repeat that "enforced in the DB"
phrase, so only the upper bound is DB-enforced here (via VARCHAR(200)
itself); the 3-char minimum is left as an app-level (Pydantic) concern for
a later phase, per the literal wording difference between the two rows.
Flagged to the human as an interpretation call, not silently assumed.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'be5a6b3416a1'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

category_enum = postgresql.ENUM(
    "water", "electricity", "sanitation", "roads", "streetlights", "other",
    name="category_enum",
    create_type=False,
)
priority_enum = postgresql.ENUM(
    "high", "normal", "low",
    name="priority_enum",
    create_type=False,
)
status_enum = postgresql.ENUM(
    "open", "in_progress", "resolved", "rejected",
    name="status_enum",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    category_enum.create(bind, checkfirst=True)
    priority_enum.create(bind, checkfirst=True)
    status_enum.create(bind, checkfirst=True)

    op.create_table(
        "complaints",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("location", sa.String(200), nullable=False),
        sa.Column("reporter_contact", sa.Text(), nullable=True),
        sa.Column("category", category_enum, nullable=False),
        sa.Column("priority", priority_enum, nullable=False),
        sa.Column("status", status_enum, nullable=False, server_default="open"),
        sa.Column("ai_summary", sa.String(140), nullable=True),
        sa.Column("triaged_by", sa.String(), nullable=False),
        sa.Column("triage_latency_ms", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "char_length(text) BETWEEN 10 AND 2000",
            name="ck_complaints_text_length",
        ),
    )

    op.create_index(
        "ix_complaints_status_priority", "complaints", ["status", "priority"]
    )
    op.create_index("ix_complaints_created_at", "complaints", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_complaints_created_at", table_name="complaints")
    op.drop_index("ix_complaints_status_priority", table_name="complaints")
    op.drop_table("complaints")

    bind = op.get_bind()
    status_enum.drop(bind, checkfirst=True)
    priority_enum.drop(bind, checkfirst=True)
    category_enum.drop(bind, checkfirst=True)
