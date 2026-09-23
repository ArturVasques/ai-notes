"""create initial schema

Revision ID: aa7cc31ac6dd
Revises:
Create Date: 2026-09-17 17:53:04.036128
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "aa7cc31ac6dd"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the initial production database schema."""

    # pgvector is part of the database schema requirements.
    # A fresh environment must not require manual setup.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.execute("""
        CREATE TABLE users (
            id UUID PRIMARY KEY,
            external_identity_id TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE notes (
            id UUID PRIMARY KEY,

            created_by UUID NOT NULL
                REFERENCES users(id)
                ON DELETE CASCADE,

            title TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE INDEX notes_created_by_idx
        ON notes (created_by)
    """)

    op.execute("""
        CREATE TABLE note_chunks (
            id UUID PRIMARY KEY,

            note_id UUID NOT NULL
                REFERENCES notes(id)
                ON DELETE CASCADE,

            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL,
            embedding VECTOR(1536) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

            UNIQUE (note_id, chunk_index)
        )
    """)

    op.execute("""
        CREATE INDEX note_chunks_embedding_hnsw_idx
        ON note_chunks
        USING hnsw (embedding vector_cosine_ops)
    """)


def downgrade() -> None:
    """Remove the initial production database schema."""

    op.execute("DROP TABLE IF EXISTS note_chunks")
    op.execute("DROP TABLE IF EXISTS notes")
    op.execute("DROP TABLE IF EXISTS users")
