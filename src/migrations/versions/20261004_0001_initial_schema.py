"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-10-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "english_texts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("level", sa.Text(), nullable=False),
        sa.Column("english_text", sa.Text(), nullable=False),
        sa.Column("word_count", sa.Integer(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "uq_english_texts_title_active",
        "english_texts",
        ["title"],
        unique=True,
        postgresql_where=sa.text("NOT is_deleted"),
    )
    op.create_table(
        "sentences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "text_id",
            sa.Integer(),
            sa.ForeignKey("english_texts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("order_no", sa.Integer(), nullable=False),
        sa.Column("paragraph_no", sa.Integer(), nullable=False),
        sa.Column("english", sa.Text(), nullable=False),
        sa.Column("japanese", sa.Text(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.UniqueConstraint("text_id", "order_no"),
    )
    op.create_table(
        "vocabulary_notebook",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("word", sa.Text(), nullable=False, unique=True),
        sa.Column("meaning", sa.Text(), nullable=True),
        sa.Column(
            "sentence_ids",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("lookup_count", sa.Integer(), server_default="1", nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "study_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "text_id",
            sa.Integer(),
            sa.ForeignKey("english_texts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reading_seconds", sa.Integer(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.CheckConstraint("reading_seconds >= 0"),
    )

    # vocabulary_notebook はGPT Siteからも更新されるため、updated_at はDB側のトリガーで維持する
    op.execute(
        """
        CREATE FUNCTION set_updated_at() RETURNS trigger AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER vocabulary_notebook_set_updated_at
        BEFORE UPDATE ON vocabulary_notebook
        FOR EACH ROW EXECUTE FUNCTION set_updated_at()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS vocabulary_notebook_set_updated_at ON vocabulary_notebook")
    op.execute("DROP FUNCTION IF EXISTS set_updated_at()")
    op.drop_table("study_sessions")
    op.drop_table("vocabulary_notebook")
    op.drop_table("sentences")
    op.drop_index("uq_english_texts_title_active", table_name="english_texts")
    op.drop_table("english_texts")
