# AI Workspace — Code Style and Patterns

---

## Module Organization

Every module has a docstring at the top:

```python
"""Brief description of the module's responsibility.

Responsibilities:
- responsibility one.
- responsibility two.

Used by:
- consumer one.
- consumer two.

Security boundary (if relevant):
- important constraints or assumptions.
"""
```

The `Used by:` section makes it easy to trace which parts of the application depend on this code and guides refactoring decisions. Security boundaries document where tenant isolation or authorization checks happen.

---

## Function Signatures

Service and repository functions use **keyword-only arguments** (enforced with `*`):

```python
async def retrieve_knowledge(
    *,
    tenant_id: UUID,
    query: str,
) -> list[RetrievalResult]:
    """Retrieve relevant knowledge for a tenant-scoped query."""
    ...
```

This ensures callers must be explicit about which argument is which and prevents accidental reordering.

---

## Security in Repositories

Repositories perform raw SQL queries and **always filter by `tenant_id`** directly in SQL:

```python
async def search_similar_chunks(
    *,
    tenant_id: UUID,
    embedding: list[float],
    limit: int,
    max_distance: float,
) -> list[RetrievalResult]:
    """Retrieve chunks scoped to the tenant."""

    # Tenant filtering must always be in SQL, never in Python
    async with pool.connection() as connection:
        rows = await connection.execute(
            """
            SELECT content, filename
            FROM document_chunks
            WHERE tenant_id = %s
            AND embedding <=> %s <= %s
            ORDER BY embedding <=> %s
            LIMIT %s
            """,
            (tenant_id, embedding, max_distance, embedding, limit),
        )
```

Repositories also include a security boundary comment explaining tenant isolation assumptions.

---

## Settings and Configuration

Configuration is loaded via cached getters, never via module-level environment variable reads:

```python
# Good
from app.core.config import get_settings

settings = get_settings()
top_k = settings.rag_top_k

# Bad
import os

CHUNK_SIZE = int(os.environ.get("RAG_CHUNK_SIZE", "512"))  # No!
```

The `get_settings()` function uses `@lru_cache` to avoid repeated validation:

```python
@lru_cache
def get_settings() -> AppSettings:
    """Load and cache application configuration."""
    return AppSettings()
```

---

## Schemas as Contracts

Pydantic schemas define validated contracts for:

- HTTP requests and responses
- AI tool results
- Retrieval payloads
- Entity representations

```python
class RetrievalResult(BaseModel):
    """A single chunk returned by semantic search."""

    content: str
    filename: str
    distance: float
    document_id: UUID
```

Schemas validate structure and types. If you receive data that does not match the schema, validation fails explicitly rather than silently.

---

## Permission Checks

Agent tools check permissions explicitly using constants from `app/auth/permissions.py`:

```python
from app.auth.permissions import KNOWLEDGE_READ


@function_tool
async def search_knowledge(
    context: RunContextWrapper[AppContext],
    query: str,
) -> str:
    if not context.context.has_permission(KNOWLEDGE_READ):
        return "Permission denied."

    results = await retrieve_knowledge(...)
    return format_results(results)
```

Constants are stored centrally to avoid typos:

```python
# app/auth/permissions.py
KNOWLEDGE_READ = "knowledge:read"
DOCUMENTS_CREATE = "documents:create"
PROFILE_READ = "profile:read"
```

---

## Error Handling

Services raise `ValueError` for domain validation failures:

```python
if len(chunks) != len(embeddings):
    raise ValueError("Every chunk must have exactly one embedding")
```

`ValueError` is caught by `app/api/errors.py` and mapped to a 400 response with a `VALIDATION_ERROR` code:

```python
# app/api/errors.py
async def handle_value_error(request: Request, exc: Exception) -> JSONResponse:
    return _error_response(
        request, status.HTTP_400_BAD_REQUEST, "VALIDATION_ERROR", str(exc)
    )
```

**Never raise `HTTPException` below the API layer.** Domain code should not know about HTTP semantics.

The only exception is `AssistantContractError` from the AI agent service, which is mapped to a 502 `UPSTREAM_ERROR`:

```python
# app/services/ai/agent_service.py
if not isinstance(output, AssistantResponse):
    raise AssistantContractError("Assistant returned an unexpected output type")


# app/api/errors.py
async def handle_assistant_contract_error(
    request: Request, exc: Exception
) -> JSONResponse:
    return _error_response(
        request,
        status.HTTP_502_BAD_GATEWAY,
        "UPSTREAM_ERROR",
        "The assistant returned an unexpected response",
    )
```

---

## Logging

Structured logging uses `structlog` with **event names in snake_case**:

```python
logger.info("document_created", document_id=doc_id, tenant_id=tenant_id)
logger.warning("request_validation_error", path=request.url.path, error=str(exc))
logger.error("unhandled_exception", error_type=type(exc).__name__)
```

The request ID is automatically bound to every log line via structlog contextvars (set in `app/core/middleware.py`):

```python
structlog.contextvars.bind_contextvars(request_id=request_id)
```

---

## Code Quality

### Ruff

All code must pass `ruff check .` and `ruff format --check .`.

The project enables these lints: `["E", "F", "I", "UP", "B", "SIM"]` and ignores FastAPI idiomatic patterns (e.g., `B008` for `Depends()` in defaults).

Run before committing:

```bash
ruff check .
ruff format .
```

### mypy

All code must pass `mypy` with:

```
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
no_implicit_optional = true
```

Function signatures must be fully annotated:

```python
async def retrieve_knowledge(
    *,
    tenant_id: UUID,
    query: str,
) -> list[RetrievalResult]:  # Return type required
    ...
```

Run before committing:

```bash
mypy
```

---

## Testing

### Unit Tests

Unit tests are located in `tests/unit/` and **do not require a database**.

They test deterministic logic in isolation:

```python
# tests/unit/test_chunking.py
def test_chunker_respects_max_size() -> None:
    chunks = chunk_text(text, chunk_size=100, overlap=10)
    assert all(len(c) <= 100 for c in chunks)
```

Unit tests may exercise the HTTP layer with `TestClient(app)` **without** the
`with` block, so the lifespan (and therefore the database pool) never runs.
Override `get_app_context` through `app.dependency_overrides` and monkeypatch
the service function the router calls; see `tests/unit/test_api_errors.py`.

Every bug fixed in this repository has a regression test named after the
behaviour it protects (`test_missing_app_env_fails_settings_loading`,
`test_large_overlap_with_uniform_tokens_has_bounded_chunk_count`, ...). Add
one before fixing the next bug.

Run with:

```bash
pytest tests/unit -v
```

### Integration Tests

Integration tests are located in `tests/integration/` and **require a real PostgreSQL database** with pgvector enabled.

They test multiple components working together, especially tenant isolation.
`tests/integration/test_tenant_isolation.py` inserts two tenants with the
same embedding vector through raw SQL, calls the real `search_similar_chunks`
repository function as tenant A and asserts tenant B's chunk never appears.
Two further tests prove the database itself rejects a document owned by a user
from another tenant and a chunk attached to a document from another tenant.
Each test cleans up with `DELETE FROM tenants`, which cascades.

Run with:

```bash
pytest tests/integration -v
```

The database pool is managed by `tests/integration/conftest.py`, opened once per session and shared across tests.

### AI Evaluations

Evaluations are located in `evals/` and run separately (they spend OpenAI credit):

```bash
python -m evals.run_evals
```

Evals measure AI behaviour and should be run before merging high-impact changes to the agent or RAG retrieval.

---

## Environment and Configuration

Never commit `.env` files.

Environment variables are documented in `.env.example`:

```bash
# Application
APP_ENV=development
LOG_LEVEL=INFO

# OpenAI
OPENAI_API_KEY=
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PASSWORD=
```

On Windows, always start the API with the custom event loop factory:

```bash
uvicorn main:app --loop app.core.event_loop:loop_factory
```

(On Linux, the flag is harmless.)

---

## Summary

| Topic | Rule |
|---|---|
| Modules | Docstring with purpose, responsibilities, `Used by`, and security boundaries |
| Functions | Keyword-only arguments; services receive tenant context from AppContext, not HTTP |
| Repositories | Raw SQL with tenant_id filtering; security boundary comment |
| Schemas | Pydantic contracts for requests, responses, AI outputs, retrieval |
| Settings | Cached getters from `app/core/config`, never module-level env reads |
| Permissions | Constants in `app/auth/permissions.py`; every tool checks permission explicitly |
| Errors | Domain: `ValueError`; AI: `AssistantContractError`; mapped in `app/api/errors.py` to `VALIDATION_ERROR` / `UPSTREAM_ERROR`; never `HTTPException` below API layer |
| Logging | `structlog` with snake_case event names; request ID automatically contextualized |
| Quality | `ruff check` and `mypy` clean; all signatures fully annotated and typed |
| Testing | `tests/unit` (no DB), `tests/integration` (real PostgreSQL), `evals` (separate, OpenAI cost) |
| Secrets | Never commit `.env` |
