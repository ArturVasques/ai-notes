"""initial finance schema

Revision ID: 0001
Revises:
Create Date: 2026-09-25

Complete baseline for the Personal Finance domain on plain PostgreSQL.
See docs/DOMAIN_MODEL.md for the meaning of every table and rule.

Integrity rules enforced here:
- money is BIGINT minor units (cents); transaction amounts are positive.
- every finance row belongs to one user, and composite (user_id, id) foreign
  keys make it impossible to reference another user's account, category,
  investment asset or expense.
- the shape of each transaction kind (which references are required or
  forbidden) is a CHECK constraint, so a half-formed transfer or an expense
  without a category cannot exist.
- referenced accounts, categories and assets cannot be deleted while used;
  they are archived instead.

Rules that need other rows (category kind matches the transaction kind,
reimbursements never exceed their expense, archived references, currency
consistency) are enforced by the application services.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the initial database schema."""

    op.execute("""
        CREATE TABLE users (
            id UUID PRIMARY KEY,
            -- Microsoft Entra object id (`oid`). Single-tenant: the oid
            -- alone identifies a person; multi-tenant would need (tid, oid).
            external_identity_id TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            -- Informational only: access tokens do not guarantee an email
            -- claim and email is never an identity key.
            email TEXT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE accounts (
            id UUID PRIMARY KEY,

            user_id UUID NOT NULL
                REFERENCES users(id)
                ON DELETE CASCADE,

            name TEXT NOT NULL,

            type TEXT NOT NULL
                CHECK (type IN (
                    'CHECKING', 'SAVINGS', 'CASH', 'BENEFITS', 'BROKERAGE'
                )),

            description TEXT NULL,

            currency CHAR(3) NOT NULL DEFAULT 'EUR'
                CHECK (currency ~ '^[A-Z]{3}$'),

            opening_balance_minor BIGINT NOT NULL DEFAULT 0,
            archived_at TIMESTAMPTZ NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

            UNIQUE (user_id, id)
        )
    """)

    op.execute("""
        CREATE UNIQUE INDEX accounts_active_name_uidx
        ON accounts (user_id, lower(name))
        WHERE archived_at IS NULL
    """)

    op.execute("""
        CREATE TABLE categories (
            id UUID PRIMARY KEY,

            user_id UUID NOT NULL
                REFERENCES users(id)
                ON DELETE CASCADE,

            name TEXT NOT NULL,

            kind TEXT NOT NULL
                CHECK (kind IN ('EXPENSE', 'INCOME')),

            icon TEXT NOT NULL
                CHECK (icon ~ '^[a-z0-9-]{1,40}$'),

            archived_at TIMESTAMPTZ NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

            UNIQUE (user_id, id)
        )
    """)

    op.execute("""
        CREATE UNIQUE INDEX categories_active_name_uidx
        ON categories (user_id, kind, lower(name))
        WHERE archived_at IS NULL
    """)

    op.execute("""
        CREATE TABLE investment_assets (
            id UUID PRIMARY KEY,

            user_id UUID NOT NULL
                REFERENCES users(id)
                ON DELETE CASCADE,

            name TEXT NOT NULL,
            symbol TEXT NULL,

            type TEXT NOT NULL
                CHECK (type IN ('ETF', 'STOCK', 'FUND', 'BOND', 'CRYPTO', 'OTHER')),

            archived_at TIMESTAMPTZ NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

            UNIQUE (user_id, id)
        )
    """)

    op.execute("""
        CREATE UNIQUE INDEX investment_assets_active_name_uidx
        ON investment_assets (user_id, lower(name))
        WHERE archived_at IS NULL
    """)

    op.execute("""
        CREATE TABLE transactions (
            id UUID PRIMARY KEY,

            user_id UUID NOT NULL
                REFERENCES users(id)
                ON DELETE CASCADE,

            kind TEXT NOT NULL
                CHECK (kind IN (
                    'INCOME', 'EXPENSE', 'TRANSFER', 'INVESTMENT', 'REIMBURSEMENT'
                )),

            amount_minor BIGINT NOT NULL
                CHECK (amount_minor > 0),

            occurred_on DATE NOT NULL,
            description TEXT NULL,

            from_account_id UUID NULL,
            to_account_id UUID NULL,
            category_id UUID NULL,
            investment_asset_id UUID NULL,
            reimburses_transaction_id UUID NULL,

            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

            UNIQUE (user_id, id),

            FOREIGN KEY (user_id, from_account_id)
                REFERENCES accounts (user_id, id),

            FOREIGN KEY (user_id, to_account_id)
                REFERENCES accounts (user_id, id),

            FOREIGN KEY (user_id, category_id)
                REFERENCES categories (user_id, id),

            FOREIGN KEY (user_id, investment_asset_id)
                REFERENCES investment_assets (user_id, id),

            FOREIGN KEY (user_id, reimburses_transaction_id)
                REFERENCES transactions (user_id, id),

            CONSTRAINT transactions_kind_shape_check CHECK (
                (
                    kind = 'EXPENSE'
                    AND from_account_id IS NOT NULL
                    AND to_account_id IS NULL
                    AND category_id IS NOT NULL
                    AND investment_asset_id IS NULL
                    AND reimburses_transaction_id IS NULL
                )
                OR (
                    kind = 'INCOME'
                    AND from_account_id IS NULL
                    AND to_account_id IS NOT NULL
                    AND category_id IS NOT NULL
                    AND investment_asset_id IS NULL
                    AND reimburses_transaction_id IS NULL
                )
                OR (
                    kind = 'TRANSFER'
                    AND from_account_id IS NOT NULL
                    AND to_account_id IS NOT NULL
                    AND from_account_id <> to_account_id
                    AND category_id IS NULL
                    AND investment_asset_id IS NULL
                    AND reimburses_transaction_id IS NULL
                )
                OR (
                    kind = 'INVESTMENT'
                    AND from_account_id IS NOT NULL
                    AND to_account_id IS NULL
                    AND category_id IS NULL
                    AND investment_asset_id IS NOT NULL
                    AND reimburses_transaction_id IS NULL
                )
                OR (
                    kind = 'REIMBURSEMENT'
                    AND from_account_id IS NULL
                    AND to_account_id IS NOT NULL
                    AND category_id IS NULL
                    AND investment_asset_id IS NULL
                    AND reimburses_transaction_id IS NOT NULL
                )
            )
        )
    """)

    # History listing and keyset pagination.
    op.execute("""
        CREATE INDEX transactions_user_history_idx
        ON transactions (user_id, occurred_on DESC, created_at DESC, id DESC)
    """)

    op.execute("""
        CREATE INDEX transactions_user_from_account_idx
        ON transactions (user_id, from_account_id)
        WHERE from_account_id IS NOT NULL
    """)

    op.execute("""
        CREATE INDEX transactions_user_to_account_idx
        ON transactions (user_id, to_account_id)
        WHERE to_account_id IS NOT NULL
    """)

    op.execute("""
        CREATE INDEX transactions_user_category_idx
        ON transactions (user_id, category_id)
        WHERE category_id IS NOT NULL
    """)

    op.execute("""
        CREATE INDEX transactions_user_investment_asset_idx
        ON transactions (user_id, investment_asset_id)
        WHERE investment_asset_id IS NOT NULL
    """)

    op.execute("""
        CREATE INDEX transactions_reimburses_idx
        ON transactions (reimburses_transaction_id)
        WHERE reimburses_transaction_id IS NOT NULL
    """)


def downgrade() -> None:
    """Remove the initial database schema."""

    op.execute("DROP TABLE IF EXISTS transactions")
    op.execute("DROP TABLE IF EXISTS investment_assets")
    op.execute("DROP TABLE IF EXISTS categories")
    op.execute("DROP TABLE IF EXISTS accounts")
    op.execute("DROP TABLE IF EXISTS users")
