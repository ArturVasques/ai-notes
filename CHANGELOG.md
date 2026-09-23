# Changelog

All notable changes to this boilerplate. Versions follow semantic versioning;
the version number lives in `pyproject.toml` and `main.py`.

## Unreleased — AI Notes domain

- Single-company application: the tenant concept (`tenants` table,
  `tenant_id` columns, `X-Tenant-Id` header, `AppContext.tenant_id`) is
  removed. `AppContext` now carries only the user identity and permissions.
- `Document` is replaced by `Note` (`id`, `created_by`, `title`, `content`,
  `created_at`) and `document_chunks` by `note_chunks`, keeping pgvector
  embeddings and the HNSW index.
- Notes are created with `POST /notes` (JSON `title` + `content`); file
  upload, `filename` and `content_type` are removed.
- Retrieval (`search_knowledge`) only returns chunks of notes created by the
  authenticated user. Sources are cited by note title.
- Permission `documents:create` (`DOCUMENTS_CREATE`) is renamed to
  `notes:create` (`NOTES_CREATE`).

## 1.0.0 (unreleased, pending final audit)

First release of the boilerplate: a FastAPI application with an OpenAI Agents
SDK assistant, tool calling, tenant-scoped RAG on PostgreSQL + pgvector,
structured outputs, header-based development identity behind a trusted
`AppContext`, Alembic migrations, unit/integration tests, AI evals, Docker
and GitHub Actions CI.

### Hardening applied before release

- `APP_ENV` is a required enum; development header authentication is only
  possible when it is exactly `development`, and an unset value stops startup.
- Windows: a shared event loop factory (`uvicorn --loop
  app.core.event_loop:loop_factory`) so psycopg's async mode works without
  `--reload`.
- Unit tests run without PostgreSQL; the pool lifecycle lives only in the
  integration suite.
- Chunker guarantees strict progress and a bounded chunk count for large
  overlaps.
- Uniform HTTP error contract (`VALIDATION_ERROR`, `UPSTREAM_ERROR`,
  `INTERNAL_ERROR`), `X-Request-ID` correlation bound into structlog, CORS
  disabled unless origins are configured.
- Settings split into `AppSettings` (app, database, RAG) and `AISettings`
  (OpenAI) so Alembic never needs an OpenAI key; embedding model and
  `VECTOR(1536)` dimension validated as an explicit contract at startup.
- Fail-fast startup when the database pool cannot open; shutdown always
  closes the pool.
- Docker image runs as a non-root user with a `HEALTHCHECK`, installs a
  pinned lock (`requirements.txt`) in its own layer and fails the build on
  lock drift (`pip check`).
- CI: ruff, mypy, unit tests without a database, integration tests with
  PostgreSQL, then a Docker Compose smoke test (build, wait for
  `/health/ready`, assert healthcheck and non-root user, seed, tear down).
- Regression tests for every bug found during the pre-release review.
