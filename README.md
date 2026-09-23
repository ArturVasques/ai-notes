# AI App Boilerplate

A production-oriented starting point for AI applications: a FastAPI backend
with an OpenAI Agents SDK assistant, tool calling, RAG over each user's
notes on PostgreSQL + pgvector, structured outputs, tests, evals, Docker and CI.

Clone it, rename it, replace the sample domain with yours, and you start from
a base that is secure, testable and understood, instead of from an empty
folder.

```text
                AI APP BOILERPLATE v1.0
                         │
        ┌────────────────┼────────────────┐
        │                │                │
   Application          AI          Infrastructure
        │                │                │
    FastAPI            Agent            Docker
    Config             Tools             Compose
    Errors             RAG               CI
    Logging            Evals             Migrations
    AppContext         Embeddings        PostgreSQL
    Auth boundary      pgvector          Tests
        │                │                │
        └────────────────┼────────────────┘
                         ↓
                   CLONE & BUILD
                         ↓
                  PROJECT DOMAIN
```

What it deliberately does **not** include: queues, workers, caches, object
storage, Kubernetes manifests, full OpenTelemetry, a real identity provider,
MCP or multiple agents. Those are added by the project that needs them.


## Architecture at a glance

```text
Client ──HTTP──► FastAPI ──► AppContext (trusted user, permissions)
                                 │
                                 ▼
                             AI Agent ── decides which tool to call
                              │     │
                   get_my_profile  search_knowledge(query)
                              │     │
                        UserRepository  RetrievalService ─► embedding ─► pgvector (HNSW)
                              │     │
                              └──┬──┘   note retrieval filtered by created_by
                                 ▼
                     Structured output (AssistantResponse) ─► JSON response
```

Principles that every extension must keep:

- The LLM reasons; application code authenticates, authorizes and persists.
- Identity comes from `AppContext`, never from model-generated arguments.
- Note ownership lives in repository SQL and database constraints.
- Retrieved notes are data, never instructions.
- Deterministic workflows (ingestion) stay deterministic; agents are used
  only where the sequence of steps is not known in advance.

Full reference: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).


## Requirements

- Docker Desktop (or Docker Engine + Compose v2) for the containerised path.
- Python 3.13 for local development and for running the tests.
- An OpenAI API key. The assistant and the embeddings call OpenAI; nothing
  else does, and the tests never do.


## Quick start (Docker)

```powershell
git clone <this repository> my-app
cd my-app
Copy-Item .env.example .env        # then set OPENAI_API_KEY in .env
docker compose up --build -d       # builds the image, runs migrations, starts the API
docker compose run --rm --no-deps api python -m app.database.seed
```

The API is at `http://localhost:8000` with Swagger UI at `/docs`. Confirm:

```powershell
curl.exe http://localhost:8000/health/ready
```

Create a note from the sample text and ask the assistant about it. The
`X-User-Id` header is the development identity of the seeded user:

```powershell
$headers = @{ "X-User-Id" = "22222222-2222-2222-2222-222222222222" }
$note = @{ title = "Recovery guidelines"; content = (Get-Content -Raw recovery-guidelines.txt) } | ConvertTo-Json
Invoke-RestMethod -Method Post http://localhost:8000/notes -Headers $headers -ContentType "application/json" -Body $note

curl.exe -X POST http://localhost:8000/chat `
  -H "Content-Type: application/json" `
  -H "X-User-Id: 22222222-2222-2222-2222-222222222222" `
  -d '{\"message\": \"What should an athlete with a RecoveryScore of 32 do?\"}'
```

`docker compose stop` / `start` keep the data; `docker compose down -v`
destroys it. Every command, including the local (non-Docker) workflow, is in
[`HELPER.md`](HELPER.md).


## Testing

| Command | Needs | Purpose |
|---|---|---|
| `pytest tests/unit -v` | nothing | Deterministic logic, HTTP error contract, config fail-safes, tool security. Runs with no database and no network. |
| `pytest tests/integration -v` | PostgreSQL + pgvector from `.env` | Note ownership and retrieval against the real database. |
| `python -m evals.run_evals` | OpenAI key, sample note created | Probabilistic assistant behaviour. Spends credit. Run on demand. |
| `ruff check . ; ruff format --check . ; mypy` | nothing | Lint, formatting, types. |

CI (`.github/workflows/ci.yml`) runs the quality gates, the unit tests
without a database, the integration tests against a PostgreSQL service, and
finally a Docker Compose smoke test that builds the image, waits for
`/health/ready`, asserts the container healthcheck and the non-root user,
runs the seed and tears everything down.

Every bug found before v1.0 has a regression test in `tests/unit` named after
the behaviour it protects. Keep that habit.


## Start a new project from this template

Six months from now, without remembering any of this, follow these steps in
order. Each one is a small, verifiable change.

**1. Get a copy with your own history.**
On GitHub, mark this repository as a *Template repository* and use *Use this
template*, or clone it and reset the history:

```powershell
git clone <this repository> my-app
cd my-app
Remove-Item -Recurse -Force .git
git init -b main
```

**2. Configure.** `Copy-Item .env.example .env`, set `OPENAI_API_KEY`. Leave
`APP_ENV=development` for your laptop. Run the Quick start above once to see
the sample domain working before you change anything.

**3. Rename.** Search and replace the project identity. This is the complete
list of places where it appears:

| What | Where |
|---|---|
| Package name and description | `pyproject.toml` (`name`, `description`) |
| API title | `main.py` (`FastAPI(title=...)`) |
| Database name | `.env.example`, `docker-compose.yml` (3 places), `.github/workflows/ci.yml` (2 places), default in `app/core/config.py` |
| Docker image / compose project | image tag in `ci.yml`; the compose project name is the folder name |
| Agent name and instructions | `app/agents/assistant.py` |
| Lock file exclusion | the `--exclude ai-workspace-production` in the regeneration command in `HELPER.md` |
| Docs | `README.md`, `docs/*.md`, `CHANGELOG.md` |

Then `pytest tests/unit -q` must still pass.

**4. Define your domain.** Decide what the assistant is for, which
structured data it needs (tables), which knowledge it needs (notes), and
which capabilities it may use (tools). Write the permission names first in
`app/auth/permissions.py`; every tool will check one of them.

**5. Schema.** Keep `users`, `notes`, `note_chunks` as they are; they carry
the ownership constraints. Add your own tables in a new Alembic revision:

```powershell
alembic revision -m "add <your tables>"     # edit migrations/versions/<id>_*.py with raw SQL
alembic upgrade head
```

Every new table that holds user-owned data gets a foreign key to its owner
(`users`) or parent, like `notes.created_by` and `note_chunks.note_id` do.
Do not change `VECTOR(1536)` unless you also change
the embedding model contract in `app/core/config.py` and re-embed.

**6. Repositories, services, tools, agent.** Follow the existing files one
to one:

| Layer | Copy from | Rule |
|---|---|---|
| Repository | `app/repositories/user_repository.py` | Raw SQL, keyword-only arguments, owner filter (`created_by`) in every user-scoped `WHERE`. |
| Service | `app/services/rag/retrieval_service.py` | Orchestrates repositories and AI calls; raises `ValueError` for domain errors. |
| Tool | `app/tools/user_tools.py` | Reads identity from `context.context`, checks a permission first, returns text for the model. |
| Agent | `app/agents/assistant.py` | Register the tool, adjust instructions and `output_type`. |
| Schema | `app/schemas/*.py` | Pydantic contracts for requests, responses and structured outputs. |
| Tests | `tests/unit/test_tools_security.py` | Add every new tool to the identity-leak and permission tests. |

Grant the new permission to the development identity in
`app/auth/dependencies.py` and to the eval context in `evals/run_evals.py`.
Replace `recovery-guidelines.txt` and `evals/cases.py` with your own sample
note and eval cases.

**7. Identity provider.** Before any non-local deployment, replace the body
of `get_app_context` in `app/auth/dependencies.py` with token validation
that produces the same `AppContext`. Nothing downstream changes. Until then,
`APP_ENV=production` answers authenticated endpoints with 501 on purpose.

**8. Ship.** `docker compose up --build -d` locally, push, let CI run the
same gates, deploy the image with `APP_ENV=production` and platform-injected
configuration. Update `CHANGELOG.md` and tag.


## Security and configuration

- **`APP_ENV` is required.** Values: `development`, `test`, `production`.
  Unset stops the application. Header identity (`X-User-Id`) works only in
  `development`.
- **`.env` is never committed** (`.gitignore`) and never shipped. Production
  injects every variable through the platform (container environment, Key
  Vault, App Configuration).
- **`docker-compose.yml` is a local development stack** with throwaway
  credentials and `APP_ENV=development`. It is not a deployment descriptor and
  there is intentionally no production compose file.
- **CORS is closed** unless `CORS_ALLOWED_ORIGINS` lists origins.
- **Tools never receive identity from the model.** `user_id` and permissions
  come from `AppContext`; a unit test fails if a tool schema ever
  exposes them.
- **Embedding model and vector dimension are a contract.** Startup fails if
  `OPENAI_EMBEDDING_MODEL` does not produce 1536 dimensions.
- **Errors are uniform and masked.** `VALIDATION_ERROR` (400),
  `UPSTREAM_ERROR` (502), `INTERNAL_ERROR` (500); every response carries
  `X-Request-ID`, which is also bound to every log line.

All variables are documented in [`.env.example`](.env.example).


## Environments

| APP_ENV | Where it runs | Identity | Configuration source |
|---|---|---|---|
| `development` | Developer laptop: `uvicorn` with `.env`, or `docker compose` | Header-based, no identity provider | `.env` or values inlined in `docker-compose.yml` |
| `test` | CI | None; tests exercise the code directly | Workflow environment variables |
| `production` | Container platform running the same image | Validated token from the identity provider; header identity rejected | Injected by the platform |


## Documentation

| Document | Read it when |
|---|---|
| [`HELPER.md`](HELPER.md) | You need the exact command (local dev, tests, Docker, dependency lock, release). |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | You want to understand why the system is shaped this way, request by request. |
| [`docs/CODESTYLE.md`](docs/CODESTYLE.md) | You are writing code and want it to look like the rest. |
| [`docs/FOLD_STRUCTURE.md`](docs/FOLD_STRUCTURE.md) | You are looking for where something lives. |
| [`CHANGELOG.md`](CHANGELOG.md) | You want to know what changed between versions. |
