# Changelog

All notable changes to Personal Finance. Versions follow semantic versioning; the
version number lives in `pyproject.toml` and `main.py`.

## Unreleased

- Personal Finance v1: complete local application.
  - Design: typographic, card-free layout with numbers first; glass
    navigation, sheets and toasts; swipeable tab pager with depth effect;
    day/night themes (night on pure black) with high-contrast text; motion
    tokens, view transitions, skeletons and pressed states, all respecting
    `prefers-reduced-motion`. Amounts display as `€24.80`.
  - Authentication: Microsoft Entra access tokens (v2) validated in the API
    (RS256 via JWKS, issuer, audience, expiry, tenant, version, scope);
    just-in-time user provisioning from `oid` with default categories;
    `GET /me`. The development `X-User-Id` header and the seed script are
    removed; tests use dependency overrides. `users.email` is nullable.
  - Reports: `/reports/overview`, `/reports/categories`, `/reports/savings`,
    `/reports/investments`, `/reports/monthly-trend` and
    `/accounts/balances`, following the domain model's metric definitions
    (effective expenses, net savings, savings rate, allocation, cash flow).
  - Frontend: mobile-first Angular app with MSAL sign-in, Bearer
    interceptor, Home, Transactions (day-grouped, filters, edit, delete),
    Quick Add (expense, income, transfer, save, invest, refund), Insights,
    Settings (accounts, categories with icons, investment assets,
    archive/restore), PWA manifest and icons.
- F1: backend finance domain. Complete baseline schema (`users`, `accounts`,
  `categories`, `investment_assets`, `transactions`) with BIGINT minor units,
  per-kind shape CHECK and composite owner foreign keys. Services,
  repositories and REST endpoints for accounts, categories (default set,
  icon keys) and investment assets with archive/restore, and for INCOME,
  EXPENSE, TRANSFER, INVESTMENT and REIMBURSEMENT transactions with
  reimbursement caps (row-locked), history filters and keyset pagination.
  403/404/409 error mapping. Unit and integration tests.
- F0: transform AI Notes into the Personal Finance baseline. Removed the
  notes domain, the OpenAI Agents SDK assistant, tools, RAG, embeddings,
  evals and pgvector. Plain PostgreSQL 18 with a clean baseline migration
  (`0001_initial_finance_schema`, users only). Renamed technical identifiers
  to `personal-finance` / `personal_finance` / "Personal Finance API",
  version 0.1.0. Domain model and roadmap in `docs/`.
- Initial AI Notes baseline: FastAPI backend, users and notes with
  owner-scoped RAG on PostgreSQL + pgvector, OpenAI Agents SDK assistant with
  tools, development header authentication behind `AppContext`, Alembic
  migrations, unit/integration tests, evals, Docker Compose and CI.
