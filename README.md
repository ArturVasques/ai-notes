# AI Notes

AI Notes is a small educational, production-oriented application: users
create notes and ask an AI assistant questions answered from their own notes.

- **Backend:** FastAPI (`API → Service → Repository`), raw SQL through psycopg.
- **Data:** PostgreSQL + pgvector. `users` → `notes` → `note_chunks`, with
  embeddings in an HNSW index. Migrations with Alembic.
- **AI:** an OpenAI Agents SDK assistant with tools (`get_my_profile`,
  `search_knowledge`) and RAG over the notes owned by the caller. Answers are
  a structured output (`AssistantResponse`) that cites note titles.

Commands for every step below are in [`HELPER.md`](HELPER.md).


## Repository layout

| Path | Contents |
|---|---|
| `backend/` | FastAPI app (`app/`), Alembic (`alembic/`), tests, evals, `Dockerfile`, `pyproject.toml` |
| `frontend/` | Angular app |
| `docker-compose.yml` | Local development stack for the whole solution |
| `.github/workflows/` | CI |

Backend commands (`pytest`, `ruff`, `mypy`, `alembic`, `uvicorn`) run from
`backend/`.


## API

| Endpoint | Purpose |
|---|---|
| `POST /notes` | Create a note from JSON `title` + `content`; it is chunked, embedded and stored. |
| `POST /chat` | Ask the assistant; it searches only the caller's notes. |
| `GET /health/live`, `GET /health/ready` | Process and database health. |

Swagger UI is at `http://localhost:8000/docs`.


## Authentication boundary

Every request is turned into a trusted `AppContext` (user id + permissions)
in `backend/app/auth/dependencies.py`. Tools and repositories read identity only from
that context, never from model-generated arguments, and note retrieval is
filtered by owner in SQL.

Today this boundary uses a development header, `X-User-Id`, accepted only
when `APP_ENV=development`. Any other environment answers authenticated
endpoints with 501 until a real identity provider replaces that function.


## Environments

| APP_ENV | Where | Identity | Configuration |
|---|---|---|---|
| `development` | Laptop (`uvicorn` + `.env`, or `docker compose`) | `X-User-Id` header | `backend/.env` / `docker-compose.yml` |
| `test` | CI | None; tests call code directly | Workflow variables |
| `production` | Container platform, same image | Not implemented yet (501) | Injected by the platform |

`APP_ENV` is required. `.env` is never committed; `backend/.env.example` documents
every variable.


## Tests

- `pytest tests/unit`: no database, no network.
- `pytest tests/integration`: real PostgreSQL + pgvector (note ownership and
  constraints).
- `python -m evals.run_evals`: real OpenAI calls against a sample note.
- `ruff check .`, `ruff format --check .`, `mypy`.

CI (`.github/workflows/ci.yml`) runs the quality gates, unit tests,
integration tests against a PostgreSQL service and a Docker Compose smoke
test.


## Docker

`docker compose up --build -d` starts PostgreSQL, runs the migrations and
starts the API. The compose file is a local development stack only; the
image runs as a non-root user with a healthcheck.


## Not included yet

Planned for later: an Angular frontend, real Entra ID authentication, Azure
deployment, asynchronous ingestion, observability beyond structured logs, and
MCP.
