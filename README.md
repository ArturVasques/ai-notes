# Personal Finance

Personal Finance is a small, mobile-first personal finance application and a
production-oriented engineering laboratory. It is designed to be used daily
on an iPhone (Safari → Add to Home Screen).

- **Backend:** FastAPI (`API → Service → Repository`), raw SQL through psycopg.
- **Data:** PostgreSQL 18. Migrations with Alembic.
- **Frontend:** Angular with Microsoft Entra ID sign-in through MSAL.
- **Domain:** accounts, categories, income, expenses, transfers, savings,
  investments and reimbursements. See [`docs/DOMAIN_MODEL.md`](docs/DOMAIN_MODEL.md).
- **Roadmap:** [`docs/ROADMAP.md`](docs/ROADMAP.md).

Current state: backend finance domain (F1): accounts, categories,
investment assets and the five transaction kinds with their integrity rules.
Reports (F2) and the financial frontend come next. There is no AI in this
phase.

Commands for every step below are in [`HELPER.md`](HELPER.md).


## Repository layout

| Path | Contents |
|---|---|
| `backend/` | FastAPI app (`app/`), Alembic (`alembic/`), tests, `Dockerfile`, `pyproject.toml` |
| `frontend/` | Angular app |
| `docs/` | Domain model and engineering roadmap |
| `docker-compose.yml` | Local development stack for the whole solution |
| `.github/workflows/` | CI |

Backend commands (`pytest`, `ruff`, `mypy`, `alembic`, `uvicorn`) run from
`backend/`.


## API

| Endpoint | Purpose |
|---|---|
| `GET/POST /accounts`, `GET/PATCH /accounts/{id}` | Accounts; archive/restore with `PATCH {"archived": true/false}`. |
| `GET/POST /categories`, `GET/PATCH /categories/{id}` | Income and expense categories with icon keys; archive/restore. |
| `GET/POST /investment-assets`, `GET/PATCH /investment-assets/{id}` | Investment destinations; archive/restore. |
| `GET/POST /transactions`, `GET/PATCH/DELETE /transactions/{id}` | Income, expense, transfer, investment and reimbursement; filters and keyset pagination. |
| `GET /health/live`, `GET /health/ready` | Process and database health. |

Money is always an integer number of cents (`amount_minor`). Rules and error
codes are documented in [`docs/DOMAIN_MODEL.md`](docs/DOMAIN_MODEL.md).
Swagger UI is at `http://localhost:8000/docs`.


## Authentication boundary

Every request is turned into a trusted `AppContext` (user id + permissions)
in `backend/app/auth/dependencies.py`. Services and repositories read
identity only from that context, never from the request body.

Today this boundary uses a development header, `X-User-Id`, accepted only
when `APP_ENV=development`. Any other environment answers authenticated
endpoints with 501 until Entra JWT validation replaces that function (next
milestone).

The Angular app signs in with MSAL and sends only the Entra Bearer access
token. Until the backend validates it, browser calls to authenticated
endpoints are expected to fail; the frontend never sends `X-User-Id`.


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
- `pytest tests/integration`: real PostgreSQL with migrations applied.
- `ruff check .`, `ruff format --check .`, `mypy`.
- Frontend: `npm test` (Vitest) and `npm run build` from `frontend/`.

CI (`.github/workflows/ci.yml`) runs the backend quality gates, unit tests,
integration tests against a PostgreSQL service and a Docker Compose smoke
test.


## Docker

`docker compose up --build -d` starts PostgreSQL 18, runs the migrations and
starts the API. The compose file is a local development stack only; the
image runs as a non-root user with a healthcheck.


## Not included yet

Reports (F2), the financial frontend, Entra JWT validation in the API, PWA configuration,
Azure deployment, asynchronous processing, observability beyond structured
logs, AI agent + tools, and MCP. See the roadmap.
