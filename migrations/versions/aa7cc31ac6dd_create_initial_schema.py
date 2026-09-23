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
        CREATE TABLE tenants (
            id UUID PRIMARY KEY,
            name TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE users (
            id UUID PRIMARY KEY,
            tenant_id UUID NOT NULL
                REFERENCES tenants(id)
                ON DELETE CASCADE,

            external_identity_id TEXT NOT NULL,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, external_identity_id),
            UNIQUE (tenant_id, email)
        )
    """)

    op.execute("""
        CREATE TABLE documents (
            id UUID PRIMARY KEY,

            tenant_id UUID NOT NULL
                REFERENCES tenants(id)
                ON DELETE CASCADE,

            uploaded_by UUID NOT NULL,

            filename TEXT NOT NULL,
            content_type TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

            UNIQUE (tenant_id, id),

            FOREIGN KEY (tenant_id, uploaded_by)
                REFERENCES users (tenant_id, id)
        )
    """)

    op.execute("""
        CREATE TABLE document_chunks (
            id UUID PRIMARY KEY,

            tenant_id UUID NOT NULL
                REFERENCES tenants(id)
                ON DELETE CASCADE,

            document_id UUID NOT NULL,

            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL,
            embedding VECTOR(1536) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

            UNIQUE (document_id, chunk_index),

            FOREIGN KEY (tenant_id, document_id)
                REFERENCES documents (tenant_id, id)
                ON DELETE CASCADE
        )
    """)

    op.execute("""
        CREATE INDEX document_chunks_embedding_hnsw_idx
        ON document_chunks
        USING hnsw (embedding vector_cosine_ops)
    """)

    op.execute("""
        CREATE INDEX document_chunks_tenant_idx
        ON document_chunks (tenant_id)
    """)


def downgrade() -> None:
    """Remove the initial production database schema."""

    op.execute("DROP TABLE IF EXISTS document_chunks")
    op.execute("DROP TABLE IF EXISTS documents")
    op.execute("DROP TABLE IF EXISTS users")
    op.execute("DROP TABLE IF EXISTS tenants")
